"""Endpoints do conselho administrativo — personas C-Level e deliberações."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.models.enums import AgentRole
from app.routes.deps import DbSession
from app.schemas.council import (
    ChiefOpinionRead,
    ChiefProfileRead,
    ChiefProfilesResponse,
    CommunicationRead,
    CommunicationsResponse,
    DeliberationRequest,
    DeliberationResponse,
    MemoryFactRequest,
)
from app.services import council_service
from app.services.council_service import Proposal

router = APIRouter(prefix="/council", tags=["conselho"])


@router.post(
    "/profiles/init",
    response_model=ChiefProfilesResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Materializa os perfis cognitivos das personas C-Level",
)
def init_profiles(session: DbSession) -> ChiefProfilesResponse:
    """Operação idempotente: perfis existentes são apenas revinculados aos agentes."""
    profiles = council_service.init_profiles(session)
    session.commit()
    return ChiefProfilesResponse(
        total=len(profiles),
        profiles=[ChiefProfileRead.model_validate(profile) for profile in profiles],
    )


@router.get("/profiles", response_model=ChiefProfilesResponse, summary="Perfis do conselho")
def list_profiles(session: DbSession) -> ChiefProfilesResponse:
    profiles = council_service.list_profiles(session)
    return ChiefProfilesResponse(
        total=len(profiles),
        profiles=[ChiefProfileRead.model_validate(profile) for profile in profiles],
    )


@router.post(
    "/deliberate",
    response_model=DeliberationResponse,
    summary="Submete uma proposta à deliberação do conselho",
)
def deliberate(payload: DeliberationRequest, session: DbSession) -> DeliberationResponse:
    """CTO, CMO e CFO opinam; o CEO consolida o veredito e resolve impasses."""
    decision = council_service.deliberate(
        session,
        Proposal(
            topic=payload.topic,
            description=payload.description,
            submitted_by=payload.submitted_by,
            context=payload.context,
        ),
    )
    session.commit()
    return DeliberationResponse(
        thread_id=decision.thread_id,
        topic=decision.proposal.topic,
        outcome=decision.outcome,
        complexity=decision.complexity,
        narrative=decision.narrative,
        conditions=list(decision.conditions),
        opinions=[
            ChiefOpinionRead(
                role=opinion.role,
                stance=opinion.stance,
                confidence=opinion.confidence,
                rationale=opinion.rationale,
                concerns=list(opinion.concerns),
            )
            for opinion in decision.opinions
        ],
    )


@router.get(
    "/communications",
    response_model=CommunicationsResponse,
    summary="Histórico de comunicações entre os Chiefs",
)
def list_communications(
    session: DbSession, thread_id: uuid.UUID | None = None, limit: int = 50
) -> CommunicationsResponse:
    messages = council_service.list_communications(session, thread_id=thread_id, limit=limit)
    return CommunicationsResponse(
        total=len(messages),
        communications=[CommunicationRead.model_validate(message) for message in messages],
    )


@router.post(
    "/profiles/{role}/memory",
    response_model=ChiefProfileRead,
    summary="Grava um fato na memória de contexto de um Chief",
)
def remember(role: AgentRole, payload: MemoryFactRequest, session: DbSession) -> ChiefProfileRead:
    try:
        profile = council_service.remember(
            session, role, payload.fact, importance=payload.importance
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    session.commit()
    return ChiefProfileRead.model_validate(profile)
