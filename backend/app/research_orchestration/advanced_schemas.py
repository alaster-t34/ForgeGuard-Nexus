from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.research_orchestration.schemas import new_id, utc_now


class GraphNodeKind(StrEnum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    COUNTEREXAMPLE = "counterexample"
    EXPERIMENT = "experiment"
    RESULT = "result"
    REVIEW = "review"
    COUNCIL_REVIEW = "council_review"
    KNOWLEDGE = "knowledge"
    CHALLENGE = "challenge"


class GraphEdgeKind(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    TESTS = "tests"
    DERIVED_FROM = "derived_from"
    REVIEWS = "reviews"
    VERIFIES = "verifies"
    CHALLENGES = "challenges"
    REVISES = "revises"
    SUPERSEDES = "supersedes"
    FORKED_FROM = "forked_from"


class EvidenceGraphNode(BaseModel):
    id: str
    branch_id: str | None = None
    kind: GraphNodeKind
    label: str
    statement: str
    source_record_id: str | None = None
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EvidenceGraphEdge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("edge"))
    source_id: str
    target_id: str
    kind: GraphEdgeKind
    branch_id: str | None = None
    rationale: str = ""
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class EvidenceGraphEdgeCreate(BaseModel):
    source_id: str
    target_id: str
    kind: GraphEdgeKind
    rationale: str = ""
    metadata: dict = Field(default_factory=dict)


class EvidenceGraphSnapshot(BaseModel):
    nodes: list[EvidenceGraphNode]
    edges: list[EvidenceGraphEdge]
    topological_order: list[str]
    generated_at: datetime = Field(default_factory=utc_now)


class CouncilRole(StrEnum):
    RESEARCHER = "researcher"
    DEVILS_ADVOCATE = "devils_advocate"
    LITERATURE_CRITIC = "literature_critic"
    EXPERIMENT_CRITIC = "experiment_critic"
    FORMAL_VERIFIER = "formal_verifier"


class CouncilVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVISE = "revise"
    NOT_APPLICABLE = "not_applicable"


class CouncilStatus(StrEnum):
    OPEN = "open"
    PASSED = "passed"
    FAILED = "failed"
    REVISION_REQUIRED = "revision_required"


class CouncilContributionCreate(BaseModel):
    role: CouncilRole
    actor_id: str
    actor_label: str
    verdict: CouncilVerdict
    summary: str
    blocking_objections: list[str] = Field(default_factory=list)
    checked_graph_node_ids: list[str] = Field(default_factory=list)


class CouncilContribution(CouncilContributionCreate):
    id: str = Field(default_factory=lambda: new_id("council-review"))
    created_at: datetime = Field(default_factory=utc_now)


class CouncilSession(BaseModel):
    id: str = Field(default_factory=lambda: new_id("council"))
    branch_id: str
    agenda: dict[str, str]
    required_graph_node_ids: list[str] = Field(default_factory=list)
    literature_node_ids: list[str] = Field(default_factory=list)
    experiment_node_ids: list[str] = Field(default_factory=list)
    contributions: list[CouncilContribution] = Field(default_factory=list)
    status: CouncilStatus = CouncilStatus.OPEN
    final_reason: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class CouncilEvaluation(BaseModel):
    session_id: str
    branch_id: str
    accepted: bool
    status: CouncilStatus
    blockers: list[str] = Field(default_factory=list)
    role_verdicts: dict[str, str] = Field(default_factory=dict)
    independent_actors: bool
    required_roles_present: bool
    generated_at: datetime = Field(default_factory=utc_now)


class KnowledgeState(StrEnum):
    ACCEPTED = "accepted"
    CHALLENGED = "challenged"
    REVISED = "revised"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class ChallengeStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class KnowledgeChallengeCreate(BaseModel):
    title: str
    description: str
    source: str
    evidence_node_ids: list[str] = Field(default_factory=list)
    raised_by: str = "researcher"


class KnowledgeChallenge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("challenge"))
    knowledge_id: str
    title: str
    description: str
    source: str
    evidence_node_ids: list[str] = Field(default_factory=list)
    raised_by: str
    status: ChallengeStatus = ChallengeStatus.OPEN
    resolution: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None


class KnowledgeVersion(BaseModel):
    id: str
    root_id: str
    version: int = 1
    branch_id: str
    title: str
    statement: str
    evidence_ids: list[str] = Field(default_factory=list)
    state: KnowledgeState = KnowledgeState.ACCEPTED
    parent_version_id: str | None = None
    successor_id: str | None = None
    challenge_ids: list[str] = Field(default_factory=list)
    accepted_at: datetime
    updated_at: datetime = Field(default_factory=utc_now)


class KnowledgeTransitionCreate(BaseModel):
    actor: str
    reason: str


class KnowledgeRevalidation(BaseModel):
    challenge_id: str
    actor: str
    rationale: str


class KnowledgeEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("knowledge-event"))
    knowledge_id: str
    action: str
    from_state: KnowledgeState | None = None
    to_state: KnowledgeState
    actor: str
    reason: str
    related_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class KnowledgeEvolutionSnapshot(BaseModel):
    versions: list[KnowledgeVersion]
    challenges: list[KnowledgeChallenge]
    events: list[KnowledgeEvent]


class SchedulerActionType(StrEnum):
    GENERATE = "generate"
    FORK = "fork"
    KILL = "kill"
    SKIP = "skip"


class SchedulerPolicy(BaseModel):
    max_live_branches: int = Field(default=16, ge=1, le=256)
    max_children_per_branch: int = Field(default=4, ge=1, le=32)
    spawn_on_counterexample: bool = True
    spawn_on_failed_or_inconclusive_experiment: bool = True
    spawn_on_cross_pollination_obstacle: bool = True
    spawn_on_knowledge_challenge: bool = True
    kill_rejected: bool = True
    kill_failed_council: bool = True


class SchedulerTickRequest(BaseModel):
    dry_run: bool = False
    policy: SchedulerPolicy = Field(default_factory=SchedulerPolicy)


class SchedulerDecision(BaseModel):
    id: str = Field(default_factory=lambda: new_id("scheduler-decision"))
    action: SchedulerActionType
    reason: str
    source_branch_id: str | None = None
    target_branch_id: str | None = None
    related_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class SchedulerRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("scheduler-run"))
    dry_run: bool
    decisions: list[SchedulerDecision] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ResearchSystemOverview(BaseModel):
    graph_nodes: int
    graph_edges: int
    council_sessions: int
    council_passed: int
    knowledge_challenged: int
    knowledge_revised: int
    knowledge_revoked: int
    scheduler_runs: int
    scheduler_actions: int
