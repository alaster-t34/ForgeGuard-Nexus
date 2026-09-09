from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.research_orchestration.advanced_schemas import (
    CouncilContributionCreate,
    CouncilEvaluation,
    CouncilSession,
    EvidenceGraphEdge,
    EvidenceGraphEdgeCreate,
    EvidenceGraphSnapshot,
    KnowledgeChallengeCreate,
    KnowledgeEvolutionSnapshot,
    KnowledgeTransitionCreate,
    KnowledgeVersion,
    ResearchSystemOverview,
    SchedulerRun,
    SchedulerTickRequest,
)
from app.research_orchestration.schemas import (
    AcceptedKnowledge,
    BranchResultUpdate,
    CounterexampleCreate,
    CounterexampleResolution,
    CrossPollinationDigest,
    CrossPollinationRequest,
    EvidenceCreate,
    ExperimentCreate,
    ExperimentUpdate,
    ResearchBranch,
    ResearchBranchCreate,
    ResearchGateReport,
    ResearchOverview,
    ReviewCreate,
)

router = APIRouter(prefix="/research", tags=["research-orchestration"])


def _research():
    from app.runtime import runtime

    return runtime.research


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/overview", response_model=ResearchOverview)
async def research_overview() -> ResearchOverview:
    return _research().overview()


@router.get("/system-overview", response_model=ResearchSystemOverview)
async def research_system_overview() -> ResearchSystemOverview:
    return _research().system_overview()


@router.get("/branches", response_model=list[ResearchBranch])
async def list_research_branches() -> list[ResearchBranch]:
    return _research().list_branches()


@router.post("/branches", response_model=ResearchBranch, status_code=status.HTTP_201_CREATED)
async def create_research_branch(payload: ResearchBranchCreate) -> ResearchBranch:
    try:
        return _research().create_branch(payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.get("/branches/{branch_id}", response_model=ResearchBranch)
async def get_research_branch(branch_id: str) -> ResearchBranch:
    try:
        return _research().get_branch(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/evidence", response_model=ResearchBranch)
async def add_research_evidence(branch_id: str, payload: EvidenceCreate) -> ResearchBranch:
    try:
        return _research().add_evidence(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/counterexamples", response_model=ResearchBranch)
async def add_counterexample(branch_id: str, payload: CounterexampleCreate) -> ResearchBranch:
    try:
        return _research().add_counterexample(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/counterexamples/{counterexample_id}/resolve", response_model=ResearchBranch)
async def resolve_counterexample(
    branch_id: str,
    counterexample_id: str,
    payload: CounterexampleResolution,
) -> ResearchBranch:
    try:
        return _research().resolve_counterexample(branch_id, counterexample_id, payload.resolution)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/experiments", response_model=ResearchBranch)
async def add_experiment(branch_id: str, payload: ExperimentCreate) -> ResearchBranch:
    try:
        return _research().add_experiment(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/experiments/{experiment_id}", response_model=ResearchBranch)
async def update_experiment(
    branch_id: str,
    experiment_id: str,
    payload: ExperimentUpdate,
) -> ResearchBranch:
    try:
        return _research().update_experiment(branch_id, experiment_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/result", response_model=ResearchBranch)
async def set_branch_result(branch_id: str, payload: BranchResultUpdate) -> ResearchBranch:
    try:
        return _research().set_result(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/reviews/critic", response_model=ResearchBranch)
async def add_critic_review(branch_id: str, payload: ReviewCreate) -> ResearchBranch:
    try:
        return _research().add_critic_review(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.post("/branches/{branch_id}/reviews/verifier", response_model=ResearchBranch)
async def add_verifier_review(branch_id: str, payload: ReviewCreate) -> ResearchBranch:
    try:
        return _research().add_verifier_review(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.post("/branches/{branch_id}/cross-pollinate", response_model=CrossPollinationDigest)
async def cross_pollinate(branch_id: str, payload: CrossPollinationRequest) -> CrossPollinationDigest:
    try:
        return _research().cross_pollinate(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/branches/{branch_id}/gate", response_model=ResearchGateReport)
async def research_gate(branch_id: str) -> ResearchGateReport:
    try:
        return _research().gate_report(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/accept", response_model=AcceptedKnowledge)
async def accept_knowledge(branch_id: str) -> AcceptedKnowledge:
    try:
        return _research().accept(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/accepted-knowledge", response_model=list[AcceptedKnowledge])
async def accepted_knowledge() -> list[AcceptedKnowledge]:
    return _research().list_accepted_knowledge()


@router.get("/cross-pollination", response_model=list[CrossPollinationDigest])
async def cross_pollination_feed() -> list[CrossPollinationDigest]:
    return _research().list_cross_pollination()


@router.get("/evidence-graph", response_model=EvidenceGraphSnapshot)
async def evidence_graph(branch_id: str | None = Query(default=None)) -> EvidenceGraphSnapshot:
    try:
        return _research().graph_snapshot(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/evidence-graph/edges", response_model=EvidenceGraphEdge, status_code=status.HTTP_201_CREATED)
async def add_evidence_graph_edge(payload: EvidenceGraphEdgeCreate) -> EvidenceGraphEdge:
    try:
        return _research().add_graph_edge(payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.post("/branches/{branch_id}/council", response_model=CouncilSession, status_code=status.HTTP_201_CREATED)
async def open_council(branch_id: str) -> CouncilSession:
    try:
        return _research().open_council(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.get("/council", response_model=list[CouncilSession])
async def list_council(branch_id: str | None = Query(default=None)) -> list[CouncilSession]:
    return _research().list_council_sessions(branch_id)


@router.post("/council/{session_id}/contributions", response_model=CouncilSession)
async def council_contribution(session_id: str, payload: CouncilContributionCreate) -> CouncilSession:
    try:
        return _research().council_contribute(session_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/council/{session_id}/evaluation", response_model=CouncilEvaluation)
async def council_evaluation(session_id: str) -> CouncilEvaluation:
    try:
        return _research().council_evaluate(session_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/scheduler/tick", response_model=SchedulerRun)
async def scheduler_tick(payload: SchedulerTickRequest) -> SchedulerRun:
    return _research().scheduler_tick(payload)


@router.get("/scheduler/runs", response_model=list[SchedulerRun])
async def scheduler_runs() -> list[SchedulerRun]:
    return _research().list_scheduler_runs()


@router.get("/knowledge-evolution", response_model=KnowledgeEvolutionSnapshot)
async def knowledge_evolution() -> KnowledgeEvolutionSnapshot:
    return _research().evolution_snapshot()


@router.post("/knowledge/{knowledge_id}/challenge", response_model=KnowledgeVersion)
async def challenge_knowledge(knowledge_id: str, payload: KnowledgeChallengeCreate) -> KnowledgeVersion:
    try:
        return _research().challenge_knowledge(knowledge_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.post("/knowledge/{knowledge_id}/revoke", response_model=KnowledgeVersion)
async def revoke_knowledge(knowledge_id: str, payload: KnowledgeTransitionCreate) -> KnowledgeVersion:
    try:
        return _research().revoke_knowledge(knowledge_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
