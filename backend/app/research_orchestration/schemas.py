from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class BranchStatus(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    BLOCKED = "blocked"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"
    ARCHIVED = "archived"


class EvidenceKind(StrEnum):
    OBSERVATION = "observation"
    DATASET = "dataset"
    LITERATURE = "literature"
    DERIVATION = "derivation"
    PROOF = "proof"
    BENCHMARK = "benchmark"
    REPLICATION = "replication"
    TOOL_OUTPUT = "tool_output"


class ExperimentStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"


class ReviewVerdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    REVISE = "revise"


class GateStage(StrEnum):
    HYPOTHESIS = "hypothesis"
    EVIDENCE = "evidence"
    CRITIC = "independent_critic"
    VERIFIER = "verifier"
    ACCEPTED = "accepted_knowledge"


class ResearchActor(BaseModel):
    id: str
    role: Literal["researcher", "critic", "verifier", "human"]
    label: str


class EvidenceRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("ev"))
    kind: EvidenceKind
    title: str
    claim: str
    source: str
    content_hash: str | None = None
    reproducible: bool = False
    metadata: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class CounterexampleRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("cx"))
    title: str
    description: str
    source: str
    resolved: bool = False
    resolution: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class ExperimentRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("exp"))
    title: str
    protocol: str
    expected_result: str
    actual_result: str | None = None
    status: ExperimentStatus = ExperimentStatus.PLANNED
    artifacts: list[str] = Field(default_factory=list)
    reproducible: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ReviewRecord(BaseModel):
    id: str = Field(default_factory=lambda: new_id("review"))
    reviewer: ResearchActor
    verdict: ReviewVerdict
    summary: str
    blocking_objections: list[str] = Field(default_factory=list)
    checked_evidence_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ResearchBranchCreate(BaseModel):
    title: str
    question: str
    hypothesis: str
    owner: str = "researcher"
    tags: list[str] = Field(default_factory=list)
    parent_branch_id: str | None = None


class ResearchBranch(BaseModel):
    id: str = Field(default_factory=lambda: new_id("branch"))
    title: str
    question: str
    hypothesis: str
    owner: str
    tags: list[str] = Field(default_factory=list)
    parent_branch_id: str | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    counterexamples: list[CounterexampleRecord] = Field(default_factory=list)
    experiments: list[ExperimentRecord] = Field(default_factory=list)
    result: str | None = None
    status: BranchStatus = BranchStatus.PROPOSED
    critic_reviews: list[ReviewRecord] = Field(default_factory=list)
    verifier_reviews: list[ReviewRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class EvidenceCreate(BaseModel):
    kind: EvidenceKind
    title: str
    claim: str
    source: str
    content_hash: str | None = None
    reproducible: bool = False
    metadata: dict = Field(default_factory=dict)


class CounterexampleCreate(BaseModel):
    title: str
    description: str
    source: str


class CounterexampleResolution(BaseModel):
    resolution: str


class ExperimentCreate(BaseModel):
    title: str
    protocol: str
    expected_result: str
    artifacts: list[str] = Field(default_factory=list)


class ExperimentUpdate(BaseModel):
    actual_result: str
    status: ExperimentStatus
    artifacts: list[str] = Field(default_factory=list)
    reproducible: bool = False


class BranchResultUpdate(BaseModel):
    result: str


class ReviewCreate(BaseModel):
    reviewer: ResearchActor
    verdict: ReviewVerdict
    summary: str
    blocking_objections: list[str] = Field(default_factory=list)
    checked_evidence_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reviewer_matches_review_type(self):
        if self.reviewer.role not in {"critic", "verifier", "human"}:
            raise ValueError("Reviewers must be critic, verifier, or human actors")
        return self


class CrossPollinationDigest(BaseModel):
    generated_at: datetime = Field(default_factory=utc_now)
    source_branch_id: str
    best_lemma: str | None = None
    best_negative_result: str | None = None
    unresolved_obstacle: str | None = None
    useful_tool: str | None = None
    target_branch_ids: list[str] = Field(default_factory=list)


class CrossPollinationRequest(BaseModel):
    best_lemma: str | None = None
    best_negative_result: str | None = None
    unresolved_obstacle: str | None = None
    useful_tool: str | None = None
    target_branch_ids: list[str] = Field(default_factory=list)


class GateCheck(BaseModel):
    name: str
    passed: bool
    detail: str


class ResearchGateReport(BaseModel):
    branch_id: str
    stage: GateStage
    accepted: bool
    checks: list[GateCheck]
    blockers: list[str]
    generated_at: datetime = Field(default_factory=utc_now)


class AcceptedKnowledge(BaseModel):
    id: str = Field(default_factory=lambda: new_id("knowledge"))
    branch_id: str
    title: str
    statement: str
    evidence_ids: list[str]
    critic_review_id: str
    verifier_review_id: str
    provenance: dict = Field(default_factory=dict)
    accepted_at: datetime = Field(default_factory=utc_now)


class ResearchOverview(BaseModel):
    branches_total: int
    active: int
    blocked: int
    under_review: int
    verified: int
    rejected: int
    accepted_knowledge: int
    cross_pollination_events: int
