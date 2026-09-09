from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.research_orchestration.autonomy_schemas import (
    AutoExperimentRequest,
    AutoExperimentRun,
    BranchBudgetAllocation,
    BranchResourceBudget,
    ContradictionPropagationEvent,
    LineageScore,
    LiteratureIngestionResult,
    LiteratureSearchRequest,
    ResearchAutonomyOverview,
)

router = APIRouter(prefix="/research", tags=["research-autonomy"])


def _autonomy():
    from app.runtime import runtime

    return runtime.research_autonomy


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


@router.get("/autonomy/overview", response_model=ResearchAutonomyOverview)
async def autonomy_overview() -> ResearchAutonomyOverview:
    return _autonomy().overview()


@router.get("/budgets", response_model=list[BranchResourceBudget])
async def branch_budgets() -> list[BranchResourceBudget]:
    return _autonomy().list_budgets()


@router.get("/branches/{branch_id}/budget", response_model=BranchResourceBudget)
async def branch_budget(branch_id: str) -> BranchResourceBudget:
    try:
        return _autonomy().budget(branch_id)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post("/branches/{branch_id}/budget", response_model=BranchResourceBudget)
async def allocate_branch_budget(
    branch_id: str,
    payload: BranchBudgetAllocation,
) -> BranchResourceBudget:
    try:
        return _autonomy().allocate_budget(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/branches/{branch_id}/auto-experiments",
    response_model=AutoExperimentRun,
    status_code=status.HTTP_201_CREATED,
)
async def run_auto_experiment(branch_id: str, payload: AutoExperimentRequest) -> AutoExperimentRun:
    try:
        return _autonomy().run_experiment(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/auto-experiments", response_model=list[AutoExperimentRun])
async def auto_experiment_runs(branch_id: str | None = Query(default=None)) -> list[AutoExperimentRun]:
    return _autonomy().list_experiment_runs(branch_id)


@router.post(
    "/branches/{branch_id}/literature",
    response_model=LiteratureIngestionResult,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_literature(branch_id: str, payload: LiteratureSearchRequest) -> LiteratureIngestionResult:
    try:
        return await _autonomy().ingest_literature(branch_id, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/literature-runs", response_model=list[LiteratureIngestionResult])
async def literature_runs(branch_id: str | None = Query(default=None)) -> list[LiteratureIngestionResult]:
    return _autonomy().list_literature_runs(branch_id)


@router.get("/lineage-scores", response_model=list[LineageScore])
async def lineage_scores() -> list[LineageScore]:
    return _autonomy().lineage_scores()


@router.post(
    "/branches/{branch_id}/counterexamples/{counterexample_id}/propagate",
    response_model=ContradictionPropagationEvent,
)
async def propagate_counterexample(branch_id: str, counterexample_id: str) -> ContradictionPropagationEvent:
    try:
        return _autonomy().propagate_counterexample(branch_id, counterexample_id)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.get("/contradictions", response_model=list[ContradictionPropagationEvent])
async def contradiction_events() -> list[ContradictionPropagationEvent]:
    return _autonomy().list_contradictions()
