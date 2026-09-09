from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from app.research_orchestration.advanced_schemas import (
    EvidenceGraphEdge,
    EvidenceGraphEdgeCreate,
    EvidenceGraphNode,
    EvidenceGraphSnapshot,
    GraphEdgeKind,
    GraphNodeKind,
)
from app.research_orchestration.schemas import (
    AcceptedKnowledge,
    CounterexampleRecord,
    EvidenceRecord,
    ExperimentRecord,
    ResearchBranch,
    ReviewRecord,
    utc_now,
)


class EvidenceGraphStore:
    """Persistent scientific evidence DAG.

    The graph is deliberately stricter than the list-shaped branch record. Every
    relationship is explicit and cycle creation is rejected. Record IDs are reused
    as node IDs where possible so provenance is easy to audit.
    """

    def __init__(self, state_path: Path):
        self.state_path = state_path
        self._lock = RLock()
        self._nodes: dict[str, EvidenceGraphNode] = {}
        self._edges: dict[str, EvidenceGraphEdge] = {}
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            self._nodes = {
                item["id"]: EvidenceGraphNode.model_validate(item)
                for item in raw.get("nodes", [])
            }
            self._edges = {
                item["id"]: EvidenceGraphEdge.model_validate(item)
                for item in raw.get("edges", [])
            }
        except (OSError, ValueError, TypeError, KeyError):
            self._nodes = {}
            self._edges = {}

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "nodes": [item.model_dump(mode="json") for item in self._nodes.values()],
            "edges": [item.model_dump(mode="json") for item in self._edges.values()],
        }
        temp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(self.state_path)

    @staticmethod
    def claim_node_id(branch_id: str) -> str:
        return f"claim:{branch_id}"

    @staticmethod
    def result_node_id(branch_id: str) -> str:
        return f"result:{branch_id}"

    def has_node(self, node_id: str) -> bool:
        return node_id in self._nodes

    def get_node(self, node_id: str) -> EvidenceGraphNode:
        node = self._nodes.get(node_id)
        if node is None:
            raise KeyError(f"Unknown evidence graph node: {node_id}")
        return node

    def _put_node(self, node: EvidenceGraphNode) -> EvidenceGraphNode:
        existing = self._nodes.get(node.id)
        if existing:
            node.created_at = existing.created_at
        node.updated_at = utc_now()
        self._nodes[node.id] = node
        return node

    def ensure_branch(self, branch: ResearchBranch) -> EvidenceGraphNode:
        with self._lock:
            node = EvidenceGraphNode(
                id=self.claim_node_id(branch.id),
                branch_id=branch.id,
                kind=GraphNodeKind.CLAIM,
                label=branch.title,
                statement=branch.hypothesis,
                source_record_id=branch.id,
                metadata={"question": branch.question, "owner": branch.owner, "tags": branch.tags},
            )
            self._put_node(node)
            if branch.parent_branch_id:
                parent_claim = self.claim_node_id(branch.parent_branch_id)
                if parent_claim in self._nodes:
                    self._ensure_edge(
                        EvidenceGraphEdgeCreate(
                            source_id=node.id,
                            target_id=parent_claim,
                            kind=GraphEdgeKind.FORKED_FROM,
                            rationale="Research branch lineage",
                        ),
                        branch_id=branch.id,
                    )
            self._persist()
            return node

    def add_evidence(self, branch: ResearchBranch, record: EvidenceRecord) -> None:
        with self._lock:
            self.ensure_branch(branch)
            node = EvidenceGraphNode(
                id=record.id,
                branch_id=branch.id,
                kind=GraphNodeKind.EVIDENCE,
                label=record.title,
                statement=record.claim,
                source_record_id=record.id,
                metadata={
                    "evidence_kind": record.kind.value,
                    "source": record.source,
                    "reproducible": record.reproducible,
                    "content_hash": record.content_hash,
                    **record.metadata,
                },
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=record.id,
                    target_id=self.claim_node_id(branch.id),
                    kind=GraphEdgeKind.SUPPORTS,
                    rationale="Evidence record attached to branch hypothesis",
                ),
                branch_id=branch.id,
            )
            self._persist()

    def add_counterexample(self, branch: ResearchBranch, record: CounterexampleRecord) -> None:
        with self._lock:
            self.ensure_branch(branch)
            node = EvidenceGraphNode(
                id=record.id,
                branch_id=branch.id,
                kind=GraphNodeKind.COUNTEREXAMPLE,
                label=record.title,
                statement=record.description,
                source_record_id=record.id,
                metadata={
                    "source": record.source,
                    "resolved": record.resolved,
                    "resolution": record.resolution,
                },
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=record.id,
                    target_id=self.claim_node_id(branch.id),
                    kind=GraphEdgeKind.CONTRADICTS,
                    rationale="Counterexample challenges the branch hypothesis",
                ),
                branch_id=branch.id,
            )
            self._persist()

    def update_counterexample(self, record: CounterexampleRecord) -> None:
        with self._lock:
            node = self.get_node(record.id)
            node.metadata["resolved"] = record.resolved
            node.metadata["resolution"] = record.resolution
            node.updated_at = utc_now()
            self._nodes[node.id] = node
            self._persist()

    def add_experiment(self, branch: ResearchBranch, record: ExperimentRecord) -> None:
        with self._lock:
            self.ensure_branch(branch)
            node = EvidenceGraphNode(
                id=record.id,
                branch_id=branch.id,
                kind=GraphNodeKind.EXPERIMENT,
                label=record.title,
                statement=record.protocol,
                source_record_id=record.id,
                metadata={
                    "expected_result": record.expected_result,
                    "actual_result": record.actual_result,
                    "status": record.status.value,
                    "artifacts": record.artifacts,
                    "reproducible": record.reproducible,
                },
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=record.id,
                    target_id=self.claim_node_id(branch.id),
                    kind=GraphEdgeKind.TESTS,
                    rationale="Experiment tests the branch hypothesis",
                ),
                branch_id=branch.id,
            )
            self._persist()

    def update_experiment(self, record: ExperimentRecord) -> None:
        with self._lock:
            node = self.get_node(record.id)
            node.metadata.update(
                actual_result=record.actual_result,
                status=record.status.value,
                artifacts=record.artifacts,
                reproducible=record.reproducible,
            )
            node.updated_at = utc_now()
            self._nodes[node.id] = node
            self._persist()

    def set_result(self, branch: ResearchBranch) -> None:
        with self._lock:
            if not branch.result:
                return
            self.ensure_branch(branch)
            node_id = self.result_node_id(branch.id)
            node = EvidenceGraphNode(
                id=node_id,
                branch_id=branch.id,
                kind=GraphNodeKind.RESULT,
                label=f"Result: {branch.title}",
                statement=branch.result,
                source_record_id=branch.id,
            )
            self._put_node(node)
            for evidence in branch.evidence:
                self._ensure_edge(
                    EvidenceGraphEdgeCreate(
                        source_id=node_id,
                        target_id=evidence.id,
                        kind=GraphEdgeKind.DERIVED_FROM,
                        rationale="Recorded result derives from branch evidence",
                    ),
                    branch_id=branch.id,
                )
            for experiment in branch.experiments:
                self._ensure_edge(
                    EvidenceGraphEdgeCreate(
                        source_id=node_id,
                        target_id=experiment.id,
                        kind=GraphEdgeKind.DERIVED_FROM,
                        rationale="Recorded result incorporates experiment outcome",
                    ),
                    branch_id=branch.id,
                )
            self._persist()

    def add_review(self, branch: ResearchBranch, review: ReviewRecord, *, verifier: bool) -> None:
        with self._lock:
            self.ensure_branch(branch)
            node = EvidenceGraphNode(
                id=review.id,
                branch_id=branch.id,
                kind=GraphNodeKind.REVIEW,
                label=f"{'Verifier' if verifier else 'Critic'}: {review.reviewer.label}",
                statement=review.summary,
                source_record_id=review.id,
                metadata={
                    "reviewer_id": review.reviewer.id,
                    "reviewer_role": review.reviewer.role,
                    "verdict": review.verdict.value,
                    "blocking_objections": review.blocking_objections,
                    "checked_evidence_ids": review.checked_evidence_ids,
                },
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=review.id,
                    target_id=self.claim_node_id(branch.id),
                    kind=GraphEdgeKind.VERIFIES if verifier else GraphEdgeKind.REVIEWS,
                    rationale="Independent review of branch hypothesis",
                ),
                branch_id=branch.id,
            )
            self._persist()

    def add_council_review(
        self,
        branch_id: str,
        review_id: str,
        label: str,
        summary: str,
        role: str,
        verdict: str,
        checked_node_ids: list[str],
    ) -> None:
        with self._lock:
            node = EvidenceGraphNode(
                id=review_id,
                branch_id=branch_id,
                kind=GraphNodeKind.COUNCIL_REVIEW,
                label=label,
                statement=summary,
                source_record_id=review_id,
                metadata={"role": role, "verdict": verdict, "checked_graph_node_ids": checked_node_ids},
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=review_id,
                    target_id=self.claim_node_id(branch_id),
                    kind=GraphEdgeKind.REVIEWS,
                    rationale="Adversarial Research Council contribution",
                ),
                branch_id=branch_id,
            )
            self._persist()

    def add_knowledge(self, knowledge: AcceptedKnowledge) -> None:
        with self._lock:
            node = EvidenceGraphNode(
                id=knowledge.id,
                branch_id=knowledge.branch_id,
                kind=GraphNodeKind.KNOWLEDGE,
                label=knowledge.title,
                statement=knowledge.statement,
                source_record_id=knowledge.id,
                metadata={"accepted_at": knowledge.accepted_at.isoformat()},
            )
            self._put_node(node)
            result_id = self.result_node_id(knowledge.branch_id)
            target = result_id if result_id in self._nodes else self.claim_node_id(knowledge.branch_id)
            if target in self._nodes:
                self._ensure_edge(
                    EvidenceGraphEdgeCreate(
                        source_id=knowledge.id,
                        target_id=target,
                        kind=GraphEdgeKind.DERIVED_FROM,
                        rationale="Accepted knowledge promoted from verified branch result",
                    ),
                    branch_id=knowledge.branch_id,
                )
            self._persist()

    def add_challenge_node(
        self,
        challenge_id: str,
        knowledge_id: str,
        branch_id: str | None,
        title: str,
        statement: str,
        source: str,
    ) -> None:
        with self._lock:
            if knowledge_id not in self._nodes:
                raise KeyError(f"Unknown knowledge graph node: {knowledge_id}")
            node = EvidenceGraphNode(
                id=challenge_id,
                branch_id=branch_id,
                kind=GraphNodeKind.CHALLENGE,
                label=title,
                statement=statement,
                source_record_id=challenge_id,
                metadata={"source": source},
            )
            self._put_node(node)
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=challenge_id,
                    target_id=knowledge_id,
                    kind=GraphEdgeKind.CHALLENGES,
                    rationale="New negative evidence challenges accepted knowledge",
                ),
                branch_id=branch_id,
            )
            self._persist()

    def link_knowledge_transition(
        self,
        new_id: str,
        old_id: str,
        kind: GraphEdgeKind,
        rationale: str,
    ) -> None:
        with self._lock:
            self._ensure_edge(
                EvidenceGraphEdgeCreate(
                    source_id=new_id,
                    target_id=old_id,
                    kind=kind,
                    rationale=rationale,
                ),
                branch_id=self._nodes.get(new_id).branch_id if new_id in self._nodes else None,
            )
            self._persist()

    def add_edge(self, payload: EvidenceGraphEdgeCreate) -> EvidenceGraphEdge:
        with self._lock:
            edge = self._ensure_edge(payload, branch_id=self.get_node(payload.source_id).branch_id)
            self._persist()
            return edge

    def _ensure_edge(self, payload: EvidenceGraphEdgeCreate, *, branch_id: str | None) -> EvidenceGraphEdge:
        if payload.source_id == payload.target_id:
            raise ValueError("Evidence graph self-loops are forbidden")
        if payload.source_id not in self._nodes:
            raise KeyError(f"Unknown evidence graph node: {payload.source_id}")
        if payload.target_id not in self._nodes:
            raise KeyError(f"Unknown evidence graph node: {payload.target_id}")
        existing = next(
            (
                item
                for item in self._edges.values()
                if item.source_id == payload.source_id
                and item.target_id == payload.target_id
                and item.kind == payload.kind
            ),
            None,
        )
        if existing:
            return existing
        edge = EvidenceGraphEdge(branch_id=branch_id, **payload.model_dump())
        self._edges[edge.id] = edge
        if self._has_cycle():
            self._edges.pop(edge.id, None)
            raise ValueError("Evidence graph edge would create a cycle; DAG invariant preserved")
        return edge

    def _has_cycle(self) -> bool:
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in self._nodes}
        indegree = {node_id: 0 for node_id in self._nodes}
        for edge in self._edges.values():
            adjacency.setdefault(edge.source_id, []).append(edge.target_id)
            indegree[edge.target_id] = indegree.get(edge.target_id, 0) + 1
        queue = [node_id for node_id, degree in indegree.items() if degree == 0]
        visited = 0
        while queue:
            current = queue.pop()
            visited += 1
            for target in adjacency.get(current, []):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
        return visited != len(indegree)

    def snapshot(self, branch_id: str | None = None) -> EvidenceGraphSnapshot:
        nodes = list(self._nodes.values())
        if branch_id is not None:
            nodes = [item for item in nodes if item.branch_id == branch_id]
        node_ids = {item.id for item in nodes}
        edges = [
            item for item in self._edges.values()
            if item.source_id in node_ids and item.target_id in node_ids
        ]
        indegree = {node_id: 0 for node_id in node_ids}
        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            adjacency[edge.source_id].append(edge.target_id)
            indegree[edge.target_id] += 1
        queue = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while queue:
            current = queue.pop(0)
            order.append(current)
            for target in sorted(adjacency.get(current, [])):
                indegree[target] -= 1
                if indegree[target] == 0:
                    queue.append(target)
                    queue.sort()
        return EvidenceGraphSnapshot(nodes=nodes, edges=edges, topological_order=order)
