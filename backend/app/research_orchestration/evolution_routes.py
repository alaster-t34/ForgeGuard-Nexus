from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.research_orchestration.advanced_schemas import KnowledgeRevalidation, KnowledgeVersion

router = APIRouter(prefix="/research/knowledge", tags=["knowledge-evolution"])


def _research():
    from app.runtime import runtime

    return runtime.research


def _not_found(exc: KeyError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _invalid(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


def _replacement(knowledge_id: str):
    accepted = next(
        (item for item in _research().list_accepted_knowledge() if item.id == knowledge_id),
        None,
    )
    if accepted is None:
        raise KeyError(f"Unknown replacement accepted knowledge: {knowledge_id}")
    return accepted


@router.post("/{knowledge_id}/revise/{replacement_knowledge_id}", response_model=KnowledgeVersion)
async def revise_knowledge(
    knowledge_id: str,
    replacement_knowledge_id: str,
    payload: KnowledgeRevalidation,
) -> KnowledgeVersion:
    """Mark the challenged version Revised and link it to a newly accepted successor.

    The replacement must already exist in Accepted Knowledge, which means it passed
    the full research gate and adversarial council before it can revise history.
    """
    try:
        replacement = _replacement(replacement_knowledge_id)
        return _research().evolution.revise(knowledge_id, replacement, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc


@router.post("/{knowledge_id}/supersede/{replacement_knowledge_id}", response_model=KnowledgeVersion)
async def supersede_knowledge(
    knowledge_id: str,
    replacement_knowledge_id: str,
    payload: KnowledgeRevalidation,
) -> KnowledgeVersion:
    """Mark the challenged version Superseded and link a verified replacement."""
    try:
        replacement = _replacement(replacement_knowledge_id)
        return _research().evolution.supersede(knowledge_id, replacement, payload)
    except KeyError as exc:
        raise _not_found(exc) from exc
    except ValueError as exc:
        raise _invalid(exc) from exc
