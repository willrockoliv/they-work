"""Endpoints da Natureza — status de recursos e governança de contratações."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.enums import AuditEventType
from app.routes.deps import DbSession, Nature
from app.schemas.resources import (
    HiringEvaluationRequest,
    HiringVerdictResponse,
    ResourceStatusResponse,
)
from app.services import agent_service, audit_service
from app.services.nature_manager import HiringRequest, NatureManager, ResourceSnapshot

router = APIRouter(prefix="/resources", tags=["natureza"])


@router.get("/status", response_model=ResourceStatusResponse, summary="Status dos recursos")
def resource_status(nature: Nature, session: DbSession) -> ResourceStatusResponse:
    """Leitura atual de RAM, VRAM e CPU com a narrativa corporativa correspondente."""
    snapshot = nature.snapshot()
    return _to_response(
        snapshot,
        nature,
        active_subagents=agent_service.count_active_subagents(session),
    )


@router.post(
    "/hiring/evaluate",
    response_model=HiringVerdictResponse,
    summary="Submeter requisição de contratação à Natureza",
)
def evaluate_hiring(
    payload: HiringEvaluationRequest, nature: Nature, session: DbSession
) -> HiringVerdictResponse:
    """Decide se o RA pode contratar, com qual modelo, ou se a vaga fica represada."""
    active_subagents = agent_service.count_active_subagents(session)
    verdict = nature.evaluate_hiring(
        HiringRequest(
            requested_by=payload.requested_by,
            job_title=payload.job_title,
            complexity=payload.complexity,
            requested_model=payload.requested_model,
        ),
        active_subagents=active_subagents,
    )

    audit_service.record_event(
        session,
        event_type=AuditEventType.NATURE_DECISION,
        actor="NATURE",
        decision=verdict.decision.value,
        summary=f"{verdict.decision.value}: {payload.job_title}",
        narrative=verdict.narrative,
        resource_snapshot=verdict.snapshot.to_dict(),
        payload={
            "requested_by": payload.requested_by,
            "complexity": payload.complexity.value,
            "requested_model": payload.requested_model,
            "granted_model": verdict.granted_model,
            "reason": verdict.reason,
        },
    )
    session.commit()

    return HiringVerdictResponse(
        decision=verdict.decision,
        allowed=verdict.allowed,
        requested_by=payload.requested_by,
        job_title=payload.job_title,
        complexity=payload.complexity,
        requested_model=payload.requested_model,
        granted_model=verdict.granted_model,
        reason=verdict.reason,
        narrative=verdict.narrative,
        queue_position=verdict.queue_position,
        resources=_to_response(verdict.snapshot, nature, active_subagents=active_subagents),
    )


def _to_response(
    snapshot: ResourceSnapshot, nature: NatureManager, *, active_subagents: int
) -> ResourceStatusResponse:
    data = snapshot.to_dict()
    data["queued_hirings"] = len(nature.pending())
    data["active_subagents"] = active_subagents
    data["max_concurrent_subagents"] = nature.settings.nature_max_concurrent_subagents
    return ResourceStatusResponse.model_validate(data)
