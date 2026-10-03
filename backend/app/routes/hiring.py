"""Endpoints do RA — requisições de contratação de subagentes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.models.enums import RequestStatus
from app.models.hiring import SubagentRequest
from app.routes.deps import DbSession, Nature
from app.routes.resources import build_resource_status
from app.schemas.agents import AgentRead
from app.schemas.hiring import (
    ClarificationRequest,
    HiringOutcomeResponse,
    SubagentRequestCreate,
    SubagentRequestRead,
    SubagentRequestsResponse,
)
from app.services import agent_service, ra_service
from app.services.nature_manager import NatureManager
from app.services.ra_service import HiringIntake, HiringOutcome

router = APIRouter(prefix="/hiring", tags=["recursos agênticos"])


@router.post(
    "/requests",
    response_model=HiringOutcomeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Abrir uma vaga junto ao RA",
)
def create_request(
    payload: SubagentRequestCreate, session: DbSession, nature: Nature
) -> HiringOutcomeResponse:
    """Pedidos vagos voltam com perguntas; os demais seguem para a auditoria da Natureza."""
    outcome = ra_service.submit_request(
        session,
        nature,
        HiringIntake(
            requested_by=payload.requested_by,
            job_title=payload.job_title,
            objective=payload.objective,
            raw_request=payload.raw_request,
            deliverables=tuple(payload.deliverables),
            tools=tuple(payload.tools),
            constraints=tuple(payload.constraints),
            specialization=payload.specialization,
            complexity=payload.complexity,
            requested_model=payload.requested_model,
        ),
    )
    session.commit()
    return _to_response(outcome, session, nature)


@router.post(
    "/requests/{request_id}/clarify",
    response_model=HiringOutcomeResponse,
    summary="Responder aos questionamentos do RA",
)
def clarify_request(
    request_id: uuid.UUID,
    payload: ClarificationRequest,
    session: DbSession,
    nature: Nature,
) -> HiringOutcomeResponse:
    request = _require_request(session, request_id)
    if not request.is_open:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Requisição já encerrada com status {request.status.value}.",
        )

    outcome = ra_service.clarify_request(
        session,
        nature,
        request,
        job_title=payload.job_title,
        objective=payload.objective,
        specialization=payload.specialization,
        deliverables=tuple(payload.deliverables) if payload.deliverables is not None else None,
        tools=tuple(payload.tools) if payload.tools is not None else None,
    )
    session.commit()
    return _to_response(outcome, session, nature)


@router.get(
    "/requests", response_model=SubagentRequestsResponse, summary="Requisições de contratação"
)
def list_requests(
    session: DbSession, request_status: RequestStatus | None = None, limit: int = 50
) -> SubagentRequestsResponse:
    requests = ra_service.list_requests(session, status=request_status, limit=limit)
    return SubagentRequestsResponse(
        total=len(requests),
        requests=[SubagentRequestRead.model_validate(item) for item in requests],
    )


@router.get(
    "/requests/{request_id}",
    response_model=SubagentRequestRead,
    summary="Detalhe de uma requisição",
)
def get_request(request_id: uuid.UUID, session: DbSession) -> SubagentRequestRead:
    return SubagentRequestRead.model_validate(_require_request(session, request_id))


def _require_request(session: Session, request_id: uuid.UUID) -> SubagentRequest:
    request = ra_service.get_request(session, request_id)
    if request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Requisição não encontrada."
        )
    return request


def _to_response(
    outcome: HiringOutcome, session: Session, nature: NatureManager
) -> HiringOutcomeResponse:
    resources = None
    if outcome.verdict is not None:
        resources = build_resource_status(
            outcome.verdict.snapshot,
            nature,
            active_subagents=agent_service.count_active_subagents(session),
        )
    return HiringOutcomeResponse(
        request=SubagentRequestRead.model_validate(outcome.request),
        agent=AgentRead.model_validate(outcome.agent) if outcome.agent else None,
        questions=list(outcome.questions),
        reused_profile=outcome.reused_profile,
        narrative=outcome.narrative,
        resources=resources,
    )
