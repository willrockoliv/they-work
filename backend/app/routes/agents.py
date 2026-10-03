"""Endpoints de gerenciamento de agentes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.models.agent import Agent
from app.models.enums import AgentType
from app.routes.deps import DbSession
from app.schemas.agents import AgentRead, AgentsStatusResponse, ChiefsInitResponse
from app.schemas.hiring import DismissalRequest
from app.services import agent_service, ra_service

router = APIRouter(prefix="/agents", tags=["agentes"])


@router.post(
    "/chiefs/init",
    response_model=ChiefsInitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inicializa os 5 Chiefs fixos (CEO, CTO, CMO, CFO, RA)",
)
def init_chiefs(session: DbSession) -> ChiefsInitResponse:
    """Operação idempotente: Chiefs já existentes são reaproveitados."""
    before = len(agent_service.list_agents(session, agent_type=AgentType.CHIEF))
    chiefs = agent_service.init_chiefs(session)
    return ChiefsInitResponse(
        created=len(chiefs) - before,
        total=len(chiefs),
        chiefs=[AgentRead.model_validate(agent) for agent in chiefs],
    )


@router.get("/status", response_model=AgentsStatusResponse, summary="Status de todos os agentes")
def agents_status(session: DbSession, include_terminated: bool = False) -> AgentsStatusResponse:
    """Panorama do quadro de funcionários da empresa virtual."""
    agents = agent_service.list_agents(session, include_terminated=include_terminated)
    chiefs = [AgentRead.model_validate(a) for a in agents if a.agent_type is AgentType.CHIEF]
    subagents = [AgentRead.model_validate(a) for a in agents if a.agent_type is AgentType.SUBAGENT]
    return AgentsStatusResponse(total=len(agents), chiefs=chiefs, subagents=subagents)


@router.post(
    "/subagents/{agent_id}/dismiss",
    response_model=AgentRead,
    summary="Demite um subagente ao fim da sprint",
)
def dismiss_subagent(
    agent_id: uuid.UUID, payload: DismissalRequest, session: DbSession
) -> AgentRead:
    """Libera a RAM ocupada; apenas o relatório final sobrevive na memória corporativa."""
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente não encontrado."
        )
    try:
        ra_service.dismiss_subagent(
            session,
            agent,
            reason=payload.reason,
            final_report=payload.final_report,
            rating=payload.rating,
        )
    except ValueError as exc:
        # 422 literal: o nome da constante está em transição no Starlette.
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return AgentRead.model_validate(agent)
