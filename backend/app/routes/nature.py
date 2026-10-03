"""Endpoints da auditoria da Natureza sobre as requisições do RA."""

from __future__ import annotations

from fastapi import APIRouter

from app.models.enums import AuditEventType
from app.routes.deps import DbSession, Nature
from app.routes.resources import build_resource_status
from app.schemas.resources import (
    HiringEvaluationRequest,
    HiringVerdictResponse,
    NatureAlertRead,
    NatureAlertsResponse,
)
from app.services import agent_service, audit_service
from app.services.nature_manager import HiringRequest

router = APIRouter(prefix="/nature", tags=["natureza"])


@router.post(
    "/audit-request",
    response_model=HiringVerdictResponse,
    summary="Auditoria da Natureza sobre uma requisição do RA",
)
def audit_request(
    payload: HiringEvaluationRequest, nature: Nature, session: DbSession
) -> HiringVerdictResponse:
    """Aprova, rebaixa o modelo, enfileira ou bloqueia a contratação, com justificativa."""
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
        summary=f"Auditoria {verdict.decision.value}: {payload.job_title}",
        narrative=verdict.narrative,
        resource_snapshot=verdict.snapshot.to_dict(),
        payload={
            "requested_by": payload.requested_by,
            "complexity": payload.complexity.value,
            "requested_model": payload.requested_model,
            "granted_model": verdict.granted_model,
            "reason": verdict.reason,
            "downgraded": verdict.granted_model != payload.requested_model
            and payload.requested_model is not None,
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
        resources=build_resource_status(
            verdict.snapshot, nature, active_subagents=active_subagents
        ),
    )


@router.get(
    "/alerts",
    response_model=NatureAlertsResponse,
    summary="Alertas corporativos emitidos pela Natureza",
)
def list_alerts(nature: Nature, session: DbSession) -> NatureAlertsResponse:
    """Avisos estruturados prontos para injeção no contexto dos agentes."""
    active_subagents = agent_service.count_active_subagents(session)
    snapshot = nature.snapshot()
    alerts = nature.alerts(snapshot, active_subagents=active_subagents)
    return NatureAlertsResponse(
        total=len(alerts),
        status=snapshot.status,
        alerts=[NatureAlertRead.model_validate(alert.to_dict()) for alert in alerts],
    )
