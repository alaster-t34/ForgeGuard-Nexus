from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    CouncilStatus,
    SchedulerActionType,
    SchedulerDecision,
    SchedulerPolicy,
    SchedulerRun,
)
from app.research_orchestration.schemas import BranchStatus, ExperimentStatus, ResearchBranchCreate


class ResearchScheduler:
    """Deterministic scheduler for branch generation, forking, and termination.

    The scheduler never invents a scientific result. It converts already recorded
    negative signals, unresolved obstacles, failed reviews and knowledge challenges
    into auditable branch-management actions.
    """

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._lock = RLock()
        self._runs: list[SchedulerRun] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._runs = [SchedulerRun.model_validate(item) for item in raw.get("runs", [])]
        except (OSError, ValueError, TypeError, KeyError):
            self._runs = []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "runs": [item.model_dump(mode="json") for item in self._runs],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    def list_runs(self) -> list[SchedulerRun]:
        return list(reversed(self._runs))

    def _processed_related_ids(self) -> set[str]:
        return {
            decision.related_id
            for run in self._runs
            if not run.dry_run
            for decision in run.decisions
            if decision.related_id
        }

    def tick(self, research, *, policy: SchedulerPolicy, dry_run: bool) -> SchedulerRun:
        with self._lock:
            decisions: list[SchedulerDecision] = []
            processed = self._processed_related_ids()
            branches = research.list_branches()
            live = [
                item for item in branches
                if item.status not in {BranchStatus.ARCHIVED, BranchStatus.REJECTED}
            ]
            children: dict[str, int] = {}
            for branch in branches:
                if branch.parent_branch_id:
                    children[branch.parent_branch_id] = children.get(branch.parent_branch_id, 0) + 1

            def can_spawn(parent_id: str | None = None) -> bool:
                if len(live) >= policy.max_live_branches:
                    return False
                if parent_id and children.get(parent_id, 0) >= policy.max_children_per_branch:
                    return False
                return True

            def register_spawn(child, parent_id: str | None = None) -> None:
                live.append(child)
                if parent_id:
                    children[parent_id] = children.get(parent_id, 0) + 1

            for branch in branches:
                if policy.kill_rejected and branch.status == BranchStatus.REJECTED:
                    decision = SchedulerDecision(
                        action=SchedulerActionType.KILL,
                        reason="Branch is explicitly rejected.",
                        source_branch_id=branch.id,
                        related_id=f"rejected:{branch.id}",
                    )
                    if decision.related_id not in processed:
                        if not dry_run:
                            research.archive_branch(branch.id, "scheduler: rejected branch")
                        decisions.append(decision)
                    continue

                if policy.kill_failed_council:
                    latest = research.council.latest_for_branch(branch.id)
                    if latest and latest.status == CouncilStatus.FAILED:
                        marker = f"council-failed:{latest.id}"
                        if marker not in processed:
                            decision = SchedulerDecision(
                                action=SchedulerActionType.KILL,
                                reason="Latest adversarial council reached a terminal FAIL verdict.",
                                source_branch_id=branch.id,
                                related_id=marker,
                            )
                            if not dry_run:
                                research.archive_branch(branch.id, "scheduler: adversarial council failed")
                            decisions.append(decision)
                        continue

                unresolved = [item for item in branch.counterexamples if not item.resolved and item.id not in processed]
                if policy.spawn_on_counterexample and unresolved and can_spawn(branch.id):
                    counterexample = unresolved[0]
                    decision = SchedulerDecision(
                        action=SchedulerActionType.FORK,
                        reason=f"Unresolved counterexample: {counterexample.title}",
                        source_branch_id=branch.id,
                        related_id=counterexample.id,
                    )
                    if not dry_run:
                        child = research.create_branch(ResearchBranchCreate(
                            title=f"Counterexample fork: {counterexample.title}",
                            question=f"Can the parent hypothesis survive or be narrowed around this counterexample? {counterexample.description}",
                            hypothesis=f"A scoped revision of '{branch.hypothesis}' can explain the counterexample without discarding supported evidence.",
                            owner=branch.owner,
                            tags=sorted(set(branch.tags + ["scheduler-fork", "counterexample"])),
                            parent_branch_id=branch.id,
                        ))
                        decision.target_branch_id = child.id
                        register_spawn(child, branch.id)
                    decisions.append(decision)
                    continue

                failed = next(
                    (
                        item for item in branch.experiments
                        if item.status in {ExperimentStatus.FAILED, ExperimentStatus.INCONCLUSIVE}
                        and item.id not in processed
                    ),
                    None,
                )
                if policy.spawn_on_failed_or_inconclusive_experiment and failed and can_spawn(branch.id):
                    decision = SchedulerDecision(
                        action=SchedulerActionType.FORK,
                        reason=f"Experiment {failed.status.value}: {failed.title}",
                        source_branch_id=branch.id,
                        related_id=failed.id,
                    )
                    if not dry_run:
                        child = research.create_branch(ResearchBranchCreate(
                            title=f"Experiment recovery fork: {failed.title}",
                            question=f"Which assumption or protocol caused the {failed.status.value} outcome in '{failed.title}'?",
                            hypothesis="At least one protocol assumption can be isolated and tested independently.",
                            owner=branch.owner,
                            tags=sorted(set(branch.tags + ["scheduler-fork", "experiment-recovery"])),
                            parent_branch_id=branch.id,
                        ))
                        decision.target_branch_id = child.id
                        register_spawn(child, branch.id)
                    decisions.append(decision)

            if policy.spawn_on_cross_pollination_obstacle:
                for event in research.list_cross_pollination():
                    marker = f"pollination:{event.generated_at.isoformat()}:{event.source_branch_id}"
                    if not event.unresolved_obstacle or marker in processed or not can_spawn():
                        continue
                    source = research.get_branch(event.source_branch_id)
                    decision = SchedulerDecision(
                        action=SchedulerActionType.GENERATE,
                        reason=f"Cross-pollination exposed unresolved obstacle: {event.unresolved_obstacle}",
                        source_branch_id=event.source_branch_id,
                        related_id=marker,
                    )
                    if not dry_run:
                        child = research.create_branch(ResearchBranchCreate(
                            title=f"Obstacle investigation: {event.unresolved_obstacle[:72]}",
                            question=f"What mechanism explains or removes this cross-branch obstacle? {event.unresolved_obstacle}",
                            hypothesis="The obstacle can be isolated into a testable subproblem with explicit evidence requirements.",
                            owner=source.owner,
                            tags=sorted(set(source.tags + ["scheduler-generated", "cross-pollination"])),
                        ))
                        decision.target_branch_id = child.id
                        register_spawn(child)
                    decisions.append(decision)
                    break

            if policy.spawn_on_knowledge_challenge:
                snapshot = research.evolution_snapshot()
                for challenge in snapshot.challenges:
                    if challenge.status.value != "open" or challenge.id in processed or not can_spawn():
                        continue
                    version = next((item for item in snapshot.versions if item.id == challenge.knowledge_id), None)
                    if version is None:
                        continue
                    decision = SchedulerDecision(
                        action=SchedulerActionType.FORK,
                        reason=f"Accepted knowledge challenged: {challenge.title}",
                        source_branch_id=version.branch_id,
                        related_id=challenge.id,
                    )
                    if not dry_run:
                        parent = research.get_branch(version.branch_id)
                        child = research.create_branch(ResearchBranchCreate(
                            title=f"Knowledge revalidation: {challenge.title}",
                            question=f"Does accepted knowledge v{version.version} survive this challenge? {challenge.description}",
                            hypothesis="The accepted statement must be retained, narrowed, revised, superseded, or revoked after adversarial revalidation.",
                            owner=parent.owner,
                            tags=sorted(set(parent.tags + ["scheduler-fork", "knowledge-revalidation"])),
                            parent_branch_id=parent.id,
                        ))
                        decision.target_branch_id = child.id
                        register_spawn(child, parent.id)
                    decisions.append(decision)
                    break

            if not decisions:
                decisions.append(SchedulerDecision(
                    action=SchedulerActionType.SKIP,
                    reason="No branch met deterministic generate/fork/kill criteria.",
                ))
            run = SchedulerRun(dry_run=dry_run, decisions=decisions)
            self._runs.append(run)
            self._persist()
            return run
