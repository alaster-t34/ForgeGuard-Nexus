from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    ChallengeStatus,
    EvidenceGraphNode,
    GraphEdgeKind,
    GraphNodeKind,
    KnowledgeChallenge,
    KnowledgeChallengeCreate,
    KnowledgeEvent,
    KnowledgeEvolutionSnapshot,
    KnowledgeRevalidation,
    KnowledgeState,
    KnowledgeTransitionCreate,
    KnowledgeVersion,
)
from app.research_orchestration.evidence_graph import EvidenceGraphStore
from app.research_orchestration.schemas import AcceptedKnowledge, new_id, utc_now


class KnowledgeEvolutionStore:
    def __init__(self, state_path: Path, graph: EvidenceGraphStore):
        self.state_path = state_path
        self.graph = graph
        self._lock = RLock()
        self._versions: dict[str, KnowledgeVersion] = {}
        self._challenges: dict[str, KnowledgeChallenge] = {}
        self._events: list[KnowledgeEvent] = []
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._versions = {item["id"]: KnowledgeVersion.model_validate(item) for item in raw.get("versions", [])}
            self._challenges = {item["id"]: KnowledgeChallenge.model_validate(item) for item in raw.get("challenges", [])}
            self._events = [KnowledgeEvent.model_validate(item) for item in raw.get("events", [])]
        except (OSError, ValueError, TypeError, KeyError):
            self._versions, self._challenges, self._events = {}, {}, []

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "versions": [item.model_dump(mode="json") for item in self._versions.values()],
            "challenges": [item.model_dump(mode="json") for item in self._challenges.values()],
            "events": [item.model_dump(mode="json") for item in self._events],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    def bootstrap(self, accepted: AcceptedKnowledge) -> KnowledgeVersion:
        with self._lock:
            existing = self._versions.get(accepted.id)
            if existing:
                return existing
            version = KnowledgeVersion(
                id=accepted.id,
                root_id=accepted.id,
                version=1,
                branch_id=accepted.branch_id,
                title=accepted.title,
                statement=accepted.statement,
                evidence_ids=accepted.evidence_ids,
                state=KnowledgeState.ACCEPTED,
                accepted_at=accepted.accepted_at,
            )
            self._versions[version.id] = version
            self._events.append(KnowledgeEvent(
                knowledge_id=version.id,
                action="accepted",
                from_state=None,
                to_state=KnowledgeState.ACCEPTED,
                actor="research-gate",
                reason="Branch passed deterministic gate and adversarial council.",
            ))
            self._persist()
            return version

    def get(self, knowledge_id: str) -> KnowledgeVersion:
        item = self._versions.get(knowledge_id)
        if item is None:
            raise KeyError(f"Unknown evolving knowledge item: {knowledge_id}")
        return item

    def challenge(self, knowledge_id: str, payload: KnowledgeChallengeCreate) -> KnowledgeVersion:
        with self._lock:
            version = self.get(knowledge_id)
            if version.state in {KnowledgeState.REVOKED, KnowledgeState.SUPERSEDED}:
                raise ValueError(f"Cannot challenge terminal knowledge state: {version.state.value}")
            unknown = [node_id for node_id in payload.evidence_node_ids if not self.graph.has_node(node_id)]
            if unknown:
                raise ValueError(f"Challenge references unknown graph nodes: {unknown}")
            challenge = KnowledgeChallenge(knowledge_id=knowledge_id, **payload.model_dump())
            self._challenges[challenge.id] = challenge
            version.challenge_ids.append(challenge.id)
            old_state = version.state
            version.state = KnowledgeState.CHALLENGED
            version.updated_at = utc_now()
            self._versions[version.id] = version
            self.graph.add_challenge_node(
                challenge.id,
                knowledge_id,
                version.branch_id,
                challenge.title,
                challenge.description,
                challenge.source,
            )
            self._events.append(KnowledgeEvent(
                knowledge_id=knowledge_id,
                action="challenged",
                from_state=old_state,
                to_state=KnowledgeState.CHALLENGED,
                actor=challenge.raised_by,
                reason=challenge.description,
                related_id=challenge.id,
            ))
            self._persist()
            return version

    def revoke(self, knowledge_id: str, payload: KnowledgeTransitionCreate) -> KnowledgeVersion:
        return self._terminal_transition(knowledge_id, KnowledgeState.REVOKED, payload)

    def _terminal_transition(self, knowledge_id: str, target: KnowledgeState, payload: KnowledgeTransitionCreate) -> KnowledgeVersion:
        with self._lock:
            version = self.get(knowledge_id)
            if version.state in {KnowledgeState.REVOKED, KnowledgeState.SUPERSEDED}:
                raise ValueError(f"Knowledge is already terminal: {version.state.value}")
            old = version.state
            version.state = target
            version.updated_at = utc_now()
            self._versions[version.id] = version
            for challenge_id in version.challenge_ids:
                challenge = self._challenges.get(challenge_id)
                if challenge and challenge.status == ChallengeStatus.OPEN:
                    challenge.status = ChallengeStatus.RESOLVED
                    challenge.resolution = payload.reason
                    challenge.resolved_at = utc_now()
            self._events.append(KnowledgeEvent(
                knowledge_id=knowledge_id,
                action=target.value,
                from_state=old,
                to_state=target,
                actor=payload.actor,
                reason=payload.reason,
            ))
            self._persist()
            return version

    def revise(self, knowledge_id: str, accepted: AcceptedKnowledge, payload: KnowledgeRevalidation) -> KnowledgeVersion:
        return self._successor(knowledge_id, accepted, payload, KnowledgeState.REVISED, GraphEdgeKind.REVISES)

    def supersede(self, knowledge_id: str, accepted: AcceptedKnowledge, payload: KnowledgeRevalidation) -> KnowledgeVersion:
        return self._successor(knowledge_id, accepted, payload, KnowledgeState.SUPERSEDED, GraphEdgeKind.SUPERSEDES)

    def _successor(
        self,
        knowledge_id: str,
        accepted: AcceptedKnowledge,
        payload: KnowledgeRevalidation,
        old_terminal_state: KnowledgeState,
        edge_kind: GraphEdgeKind,
    ) -> KnowledgeVersion:
        with self._lock:
            current = self.get(knowledge_id)
            if current.state != KnowledgeState.CHALLENGED:
                raise ValueError("Only challenged knowledge can enter revalidation transition")
            challenge = self._challenges.get(payload.challenge_id)
            if challenge is None or challenge.knowledge_id != knowledge_id:
                raise KeyError(f"Unknown challenge for knowledge item: {payload.challenge_id}")
            if challenge.status != ChallengeStatus.OPEN:
                raise ValueError("Challenge is already resolved")
            siblings = [item.version for item in self._versions.values() if item.root_id == current.root_id]
            successor = KnowledgeVersion(
                id=new_id("knowledge-version"),
                root_id=current.root_id,
                version=max(siblings or [0]) + 1,
                branch_id=accepted.branch_id,
                title=accepted.title,
                statement=accepted.statement,
                evidence_ids=accepted.evidence_ids,
                state=KnowledgeState.ACCEPTED,
                parent_version_id=current.id,
                accepted_at=accepted.accepted_at,
            )
            old_state = current.state
            current.state = old_terminal_state
            current.successor_id = successor.id
            current.updated_at = utc_now()
            challenge.status = ChallengeStatus.RESOLVED
            challenge.resolution = payload.rationale
            challenge.resolved_at = utc_now()
            self._versions[current.id] = current
            self._versions[successor.id] = successor
            self._challenges[challenge.id] = challenge

            self.graph._put_node(EvidenceGraphNode(
                id=successor.id,
                branch_id=accepted.branch_id,
                kind=GraphNodeKind.KNOWLEDGE,
                label=accepted.title,
                statement=accepted.statement,
                source_record_id=successor.id,
                metadata={
                    "root_id": successor.root_id,
                    "version": successor.version,
                    "accepted_from": accepted.id,
                },
            ))
            self.graph.link_knowledge_transition(successor.id, current.id, edge_kind, payload.rationale)
            self._events.append(KnowledgeEvent(
                knowledge_id=current.id,
                action=old_terminal_state.value,
                from_state=old_state,
                to_state=old_terminal_state,
                actor=payload.actor,
                reason=payload.rationale,
                related_id=successor.id,
            ))
            self._events.append(KnowledgeEvent(
                knowledge_id=successor.id,
                action="accepted_successor",
                from_state=None,
                to_state=KnowledgeState.ACCEPTED,
                actor=payload.actor,
                reason=payload.rationale,
                related_id=current.id,
            ))
            self._persist()
            return successor

    def snapshot(self) -> KnowledgeEvolutionSnapshot:
        return KnowledgeEvolutionSnapshot(
            versions=sorted(self._versions.values(), key=lambda item: (item.root_id, item.version)),
            challenges=sorted(self._challenges.values(), key=lambda item: item.created_at, reverse=True),
            events=list(reversed(self._events)),
        )
