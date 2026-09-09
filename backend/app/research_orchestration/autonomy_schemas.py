from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from app.research_orchestration.schemas import ExperimentStatus, new_id, utc_now


class BudgetStatus(StrEnum):
    ACTIVE = "active"
    EXHAUSTED = "exhausted"


class BranchBudgetLimits(BaseModel):
    max_experiment_runs: int = Field(default=12, ge=0, le=10000)
    max_literature_queries: int = Field(default=12, ge=0, le=10000)
    max_citations_ingested: int = Field(default=60, ge=0, le=100000)
    max_compute_units: int = Field(default=100, ge=0, le=1000000)


class BranchBudgetAllocation(BaseModel):
    limits: BranchBudgetLimits


class BranchResourceBudget(BaseModel):
    branch_id: str
    limits: BranchBudgetLimits = Field(default_factory=BranchBudgetLimits)
    spent_experiment_runs: int = 0
    spent_literature_queries: int = 0
    spent_citations_ingested: int = 0
    spent_compute_units: int = 0
    status: BudgetStatus = BudgetStatus.ACTIVE
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def utilization(self) -> dict[str, float]:
        def ratio(spent: int, limit: int) -> float:
            if limit <= 0:
                return 1.0 if spent > 0 else 0.0
            return min(1.0, spent / limit)

        return {
            "experiment_runs": ratio(self.spent_experiment_runs, self.limits.max_experiment_runs),
            "literature_queries": ratio(self.spent_literature_queries, self.limits.max_literature_queries),
            "citations_ingested": ratio(self.spent_citations_ingested, self.limits.max_citations_ingested),
            "compute_units": ratio(self.spent_compute_units, self.limits.max_compute_units),
        }


class AutoExperimentKind(StrEnum):
    NUMERIC_THRESHOLD = "numeric_threshold"
    GRAPH_INTEGRITY = "graph_integrity"
    EVIDENCE_REPLAY = "evidence_replay"
    BRANCH_CONSISTENCY = "branch_consistency"


class AutoExperimentRequest(BaseModel):
    title: str
    kind: AutoExperimentKind
    expected_result: str
    parameters: dict = Field(default_factory=dict)
    compute_units: int = Field(default=1, ge=1, le=1000)


class AutoExperimentRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("auto-exp"))
    branch_id: str
    experiment_id: str
    kind: AutoExperimentKind
    status: ExperimentStatus
    actual_result: str
    metrics: dict = Field(default_factory=dict)
    artifact_uri: str
    compute_units: int
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime = Field(default_factory=utc_now)


class LiteratureRelation(StrEnum):
    CONTEXT = "context"
    SUPPORT = "support"
    CHALLENGE = "challenge"


class LiteratureSearchRequest(BaseModel):
    query: str
    scope: Literal["internal", "academic", "web", "all"] = "academic"
    max_results: int = Field(default=5, ge=1, le=12)
    relation: LiteratureRelation = LiteratureRelation.CONTEXT
    purpose: str = "scientific literature evidence retrieval"


class LiteratureIngestionResult(BaseModel):
    branch_id: str
    query: str
    provider: str
    evidence_ids: list[str] = Field(default_factory=list)
    counterexample_ids: list[str] = Field(default_factory=list)
    citations_ingested: int = 0
    policy_notes: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class LineageScore(BaseModel):
    branch_id: str
    parent_branch_id: str | None = None
    depth: int
    descendant_count: int
    score: float = Field(ge=0, le=100)
    factors: dict[str, float] = Field(default_factory=dict)
    penalties: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)


class ContradictionTrigger(StrEnum):
    COUNTEREXAMPLE = "counterexample"
    KNOWLEDGE_CHALLENGE = "knowledge_challenge"


class ContradictionPropagationEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("contradiction-propagation"))
    trigger: ContradictionTrigger
    source_id: str
    origin_branch_id: str
    affected_branch_ids: list[str] = Field(default_factory=list)
    affected_knowledge_ids: list[str] = Field(default_factory=list)
    inherited_counterexample_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ResearchAutonomyOverview(BaseModel):
    branches_total: int
    experiment_runs: int
    literature_searches: int
    citations_ingested: int
    budgets_exhausted: int
    contradiction_events: int
