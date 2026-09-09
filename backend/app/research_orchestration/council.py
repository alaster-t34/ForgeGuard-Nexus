from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    CouncilContribution,
    CouncilContributionCreate,
    CouncilEvaluation,
    CouncilRole,
    CouncilSession,
    CouncilStatus,
    CouncilVerdict,
)
from app.research_orchestration.evidence_graph import EvidenceGraphStore
from app.research_orchestration.schemas import ResearchBranch, utc_now


class AdversarialResearchCouncil:
    REQUIRED_ROLES = {
        CouncilRole.RESEARCHER,
        CouncilRole.DEVILS_ADVOCATE,
        CouncilRole.LITERATURE_CRITIC,
        CouncilRole.EXPERIMENT_CRITIC,
        CouncilRole.FORMAL_VERIFIER,
    }

    def __init__(self, state_path: Path, graph: EvidenceGraphStore):
        self.state_path = state_path
        self.graph = graph
        self._lock = RLock()
        self._sessions: dict[str, CouncilSession] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._sessions = {
                item["id"]: CouncilSession.model_validate(item)
                for item in raw.get("sessions", [])
            }
        except (OSError, ValueError, TypeError, KeyError):
            self._sessions = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "sessions": [item.model_dump(mode="json") for item in self._sessions.values()],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    def _session(self, session_id: str) -> CouncilSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Unknown council session: {session_id}")
        return session

    def list_sessions(self, branch_id: str | None = None) -> list[CouncilSession]:
        sessions = list(self._sessions.values())
        if branch_id is not None:
            sessions = [item for item in sessions if item.branch_id == branch_id]
        return sorted(sessions, key=lambda item: item.updated_at, reverse=True)

    def latest_for_branch(self, branch_id: str) -> CouncilSession | None:
        sessions = self.list_sessions(branch_id)
        return sessions[0] if sessions else None

    def open_session(self, branch: ResearchBranch) -> CouncilSession:
        with self._lock:
            snapshot = self.graph.snapshot(branch.id)
            literature = [
                node.id for node in snapshot.nodes
                if node.kind.value == "evidence" and node.metadata.get("evidence_kind") == "literature"
            ]
            experiments = [node.id for node in snapshot.nodes if node.kind.value == "experiment"]
            required_nodes = [node.id for node in snapshot.nodes if node.kind.value in {"claim", "result", "evidence", "counterexample", "experiment"}]
            session = CouncilSession(
                branch_id=branch.id,
                agenda={
                    "question": branch.question,
                    "hypothesis": branch.hypothesis,
                    "result": branch.result or "",
                },
                required_graph_node_ids=sorted(required_nodes),
                literature_node_ids=sorted(literature),
                experiment_node_ids=sorted(experiments),
            )
            self._sessions[session.id] = session
            self._persist()
            return session

    def contribute(self, session_id: str, payload: CouncilContributionCreate) -> CouncilSession:
        with self._lock:
            session = self._session(session_id)
            graph_node_ids = {node.id for node in self.graph.snapshot(session.branch_id).nodes}
            unknown = set(payload.checked_graph_node_ids) - graph_node_ids
            if unknown:
                raise ValueError(f"Council contribution references unknown graph nodes: {sorted(unknown)}")
            session.contributions = [item for item in session.contributions if item.role != payload.role]
            contribution = CouncilContribution(**payload.model_dump())
            session.contributions.append(contribution)
            session.updated_at = utc_now()
            self.graph.add_council_review(
                session.branch_id,
                contribution.id,
                f"{payload.role.value}: {payload.actor_label}",
                payload.summary,
                payload.role.value,
                payload.verdict.value,
                payload.checked_graph_node_ids,
            )
            evaluation = self.evaluate(session.id)
            session.status = evaluation.status
            session.final_reason = "; ".join(evaluation.blockers) if evaluation.blockers else "All adversarial council checks passed."
            self._sessions[session.id] = session
            self._persist()
            return session

    def evaluate(self, session_id: str) -> CouncilEvaluation:
        session = self._session(session_id)
        latest = {item.role: item for item in session.contributions}
        missing = sorted(role.value for role in self.REQUIRED_ROLES - set(latest))
        blockers: list[str] = []
        if missing:
            blockers.append(f"missing_roles:{','.join(missing)}")

        actor_ids = [item.actor_id for item in latest.values()]
        independent_actors = len(actor_ids) == len(set(actor_ids))
        if not independent_actors:
            blockers.append("council_actor_identity_collision")

        for role, item in latest.items():
            if item.verdict in {CouncilVerdict.FAIL, CouncilVerdict.REVISE}:
                blockers.append(f"{role.value}:{item.verdict.value}")
            if item.blocking_objections:
                blockers.append(f"{role.value}:blocking_objections")
            if role in {CouncilRole.DEVILS_ADVOCATE, CouncilRole.FORMAL_VERIFIER} and not item.checked_graph_node_ids:
                blockers.append(f"{role.value}:no_graph_coverage")

        literature = latest.get(CouncilRole.LITERATURE_CRITIC)
        if session.literature_node_ids:
            if literature is None or not set(session.literature_node_ids).issubset(set(literature.checked_graph_node_ids)):
                blockers.append("literature_critic_incomplete_coverage")

        experiment = latest.get(CouncilRole.EXPERIMENT_CRITIC)
        if session.experiment_node_ids:
            if experiment is None or not set(session.experiment_node_ids).issubset(set(experiment.checked_graph_node_ids)):
                blockers.append("experiment_critic_incomplete_coverage")

        formal = latest.get(CouncilRole.FORMAL_VERIFIER)
        if formal is not None and session.required_graph_node_ids:
            if not set(session.required_graph_node_ids).issubset(set(formal.checked_graph_node_ids)):
                blockers.append("formal_verifier_incomplete_graph_coverage")

        required_roles_present = not missing
        if not required_roles_present:
            status = CouncilStatus.OPEN
        elif any(":fail" in item for item in blockers):
            status = CouncilStatus.FAILED
        elif blockers:
            status = CouncilStatus.REVISION_REQUIRED
        else:
            status = CouncilStatus.PASSED

        return CouncilEvaluation(
            session_id=session.id,
            branch_id=session.branch_id,
            accepted=status == CouncilStatus.PASSED,
            status=status,
            blockers=blockers,
            role_verdicts={role.value: item.verdict.value for role, item in latest.items()},
            independent_actors=independent_actors,
            required_roles_present=required_roles_present,
        )

    def branch_passed(self, branch_id: str) -> bool:
        session = self.latest_for_branch(branch_id)
        return bool(session and self.evaluate(session.id).accepted)
