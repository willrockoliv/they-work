"""Canais WebSocket — empurram o raciocínio dos agentes para o frontend em tempo real.

No `accept`, o cliente recebe primeiro os passos já persistidos (replay) e só então
o fluxo ao vivo: isso elimina a janela de corrida entre conectar e começar a receber.
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.config.logging import get_logger
from app.routes.deps import DbSession
from app.services import reasoning_service
from app.services.reasoning_broker import Subscription, get_broker

logger = get_logger(__name__)

router = APIRouter(tags=["observabilidade"])

#: Mantém a conexão viva quando não há atividade cognitiva.
HEARTBEAT_SECONDS = 20.0


@router.websocket("/ws/agents/{agent_id}/reasoning")
async def agent_reasoning_stream(
    websocket: WebSocket, agent_id: uuid.UUID, session: DbSession
) -> None:
    """Fluxo cognitivo de um único agente."""
    await _stream(websocket, agent_id, session)


@router.websocket("/ws/reasoning")
async def global_reasoning_stream(websocket: WebSocket) -> None:
    """Fluxo cognitivo de todos os agentes (visão onisciente)."""
    await _stream(websocket, None, None)


async def _stream(
    websocket: WebSocket, agent_id: uuid.UUID | None, session: Session | None
) -> None:
    await websocket.accept()
    broker = get_broker()
    subscription = broker.subscribe(agent_id)
    try:
        if agent_id is not None and session is not None:
            await _replay(websocket, agent_id, session)
        await _pump(websocket, subscription)
    except WebSocketDisconnect:
        logger.info("ws.reasoning_disconnected", agent_id=str(agent_id) if agent_id else "*")
    finally:
        broker.unsubscribe(subscription)


async def _replay(websocket: WebSocket, agent_id: uuid.UUID, db: Session) -> None:
    """Envia o histórico da sessão corrente antes de ligar o stream ao vivo."""
    session = reasoning_service.latest_for_agent(db, agent_id)
    if session is None:
        await websocket.send_json({"event": "replay", "session_id": None, "data": None})
        return
    steps = [step.to_dict() for step in reasoning_service.list_steps(db, session.id)]
    await websocket.send_json(
        {
            "event": "replay",
            "session_id": str(session.id),
            "data": {
                "id": str(session.id),
                "agent_id": str(agent_id),
                "task": session.task,
                "status": session.status.value,
                "model_name": session.model_name,
                "step_count": session.step_count,
                "steps": steps,
            },
        }
    )


async def _pump(websocket: WebSocket, subscription: Subscription) -> None:
    while True:
        try:
            event = await asyncio.wait_for(subscription.next_event(), timeout=HEARTBEAT_SECONDS)
        except TimeoutError:
            await websocket.send_json({"event": "heartbeat"})
            continue
        await websocket.send_json(event)
