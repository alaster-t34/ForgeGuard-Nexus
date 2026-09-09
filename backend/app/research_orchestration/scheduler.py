from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    SchedulerActionType,
    SchedulerDecision,
    SchedulerPolicy,
    SchedulerRun,
)
from app.research_orchestration.schemas import BranchStatus, ExperimentStatus, ResearchBranchCreate


class ResearchScheduler:
    """Deterministic research branch scheduler.

    It does not hallucinate scientific claims. It turns explicit negative signals,
    obstacles and challenges into auditable fork/generate/kill decisions.
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

    def tick(self, research, *, policy: SchedulerPolicy, dry_run: bool) -> SchedulerRun:
        with self._lock:
            decisions: list[SchedulerDecision] = []
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

            for branch in branches:
                if policy.kill_rejected and branch.status == BranchStatus.REJECTED:
                    decisions.append(SchedulerDecision(
                        action=SchedulerActionType.KILL,
                        reason="Branch is explicitly rejected.",
                        source_branch_id=branch.id,
                    ))
                    if not dry_run:
                        research.archive_branch(branch.id, "scheduler: rejected branch")
                    continue

                unresolved = [item for item in branch.counterexamples if not item.resolved]
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
                        live.append(child)
                        children[branch.id] = children.get(branch.id, 0) + 1
                    decisions.append(decision)
                    continue

                failed = next(
                    (
                        item for item in branch.experiments
                        if item.status in {ExperimentStatus.FAILED, ExperimentStatus.INCONCLUSIVE}
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
                        live.append(child)
                        children[branch.id] = children.get(branch.id, 0) + 1
                    decisions.append(decision)

            if not decisions:
                decisions.append(SchedulerDecision(
                    action=SchedulerActionType.SKIP,
                    reason="No branch met deterministic generate/fork/kill criteria.",
                ))
            run = SchedulerRun(dry_run=dry_run, decisions=decisions)
            self._runs.append(run)
            self._persist()
            return run
