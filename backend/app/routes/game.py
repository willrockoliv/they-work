"""Endpoints do mundo 2D — planta do escritório, estado do jogo e movimentação."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.routes.deps import AppSettings, DbSession, Nature
from app.schemas.game import (
    ChatHistoryResponse,
    GameStateResponse,
    MoveRequest,
    OfficeLayoutResponse,
    PositionRead,
)
from app.services import agent_service, game_service, office_map
from app.services.reasoning_broker import get_broker

router = APIRouter(tags=["mundo 2d"])


@router.get("/game/map", response_model=OfficeLayoutResponse, summary="Planta do escritório")
def office_layout() -> OfficeLayoutResponse:
    """Layout estático: cômodos, postos de trabalho e pontos de interesse."""
    return OfficeLayoutResponse.model_validate(office_map.layout_dict())


@router.get("/game/state", response_model=GameStateResponse, summary="Estado completo do mundo")
def game_state(
    session: DbSession,
    nature: Nature,
    settings: AppSettings,
    include_terminated: bool = False,
) -> GameStateResponse:
    """Snapshot inicial consumido pelo frontend antes de abrir o WebSocket."""
    snapshot = game_service.build_snapshot(
        session, nature, settings, include_terminated=include_terminated
    )
    return GameStateResponse.model_validate(snapshot.to_dict())


@router.get(
    "/game/chat-history",
    response_model=ChatHistoryResponse,
    summary="Falas recentes do log de comunicações",
)
def chat_history(
    session: DbSession,
    limit: int = Query(default=200, ge=1, le=500),
) -> ChatHistoryResponse:
    """Reconstrói o log a partir do raciocínio persistido, para sobreviver a recarregamentos."""
    return ChatHistoryResponse.model_validate(
        {"messages": game_service.chat_history(session, limit=limit)}
    )


@router.get(
    "/agents/{agent_id}/position",
    response_model=PositionRead,
    summary="Posição de um agente no escritório",
)
def agent_position(agent_id: uuid.UUID, session: DbSession) -> PositionRead:
    _agent_or_404(session, agent_id)
    placement = _refresh(session).get(agent_id)
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente sem lotação no escritório."
        )
    return PositionRead.model_validate(placement.to_dict())


@router.post(
    "/agents/{agent_id}/move",
    response_model=PositionRead,
    summary="Move um agente para um tile do escritório",
)
def move_agent(agent_id: uuid.UUID, payload: MoveRequest, session: DbSession) -> PositionRead:
    """O movimento manual sobrepõe o posto fixo até que o agente seja chamado de volta."""
    _agent_or_404(session, agent_id)
    _refresh(session)
    if payload.x >= office_map.GRID_COLUMNS or payload.y >= office_map.GRID_ROWS:
        raise HTTPException(status_code=422, detail="Destino fora dos limites do escritório.")
    placement = office_map.get_office_map().move(agent_id, payload.x, payload.y)
    data = placement.to_dict()
    get_broker().publish(
        {"event": "agent.moved", "agent_id": str(agent_id), "data": data}, agent_id=agent_id
    )
    return PositionRead.model_validate(data)


@router.post(
    "/agents/{agent_id}/recall",
    response_model=PositionRead,
    summary="Devolve um agente ao seu posto fixo",
)
def recall_agent(agent_id: uuid.UUID, session: DbSession) -> PositionRead:
    _agent_or_404(session, agent_id)
    _refresh(session)
    placement = office_map.get_office_map().recall(agent_id)
    if placement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Agente sem lotação no escritório."
        )
    data = placement.to_dict()
    get_broker().publish(
        {"event": "agent.moved", "agent_id": str(agent_id), "data": data}, agent_id=agent_id
    )
    return PositionRead.model_validate(data)


def _agent_or_404(session: Session, agent_id: uuid.UUID) -> Agent:
    agent = session.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Agente {agent_id} não encontrado."
        )
    return agent


def _refresh(session: Session) -> dict[uuid.UUID, office_map.Placement]:
    """Garante que todo agente vivo tenha posto antes de ler ou mover."""
    return office_map.get_office_map().place_all(agent_service.list_agents(session))
