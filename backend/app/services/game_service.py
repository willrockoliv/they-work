"""Estado do mundo 2D — consolida quadro de pessoal, lotação, recursos e relógio.

A Fase 4 não introduziu tabelas: este serviço é uma projeção de leitura sobre o
que as Fases 1 a 3 já persistem, somada à lotação em memória do `office_map`.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.models.agent import Agent
from app.models.enums import AgentStatus, AgentType, ReasoningStatus
from app.models.reasoning import ReasoningSession, ReasoningStep
from app.services import agent_service, office_map, reasoning_metrics
from app.services.nature_manager import NatureManager

#: Marco zero do relógio corporativo (fixado no boot do processo).
PROCESS_STARTED_AT = datetime.now(UTC)

#: Quantas sessões recentes são varridas para descobrir a atual de cada agente.
_RECENT_SESSION_WINDOW = 200

#: Quantas sessões recentes alimentam o histórico do log de comunicações.
_CHAT_SESSION_WINDOW = 100

#: Status que, no feed ao vivo, viram fala de sistema ao terminar.
_FAILED_STATUSES = frozenset({ReasoningStatus.FAILED, ReasoningStatus.CANCELLED})


@dataclass(frozen=True, slots=True)
class GameSnapshot:
    """Fotografia completa do mundo, pronta para serialização."""

    clock: dict[str, Any]
    resources: dict[str, Any]
    economy: dict[str, Any]
    agents: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "clock": self.clock,
            "resources": self.resources,
            "economy": self.economy,
            "layout": office_map.layout_dict(),
            "agents": list(self.agents),
        }


def build_snapshot(
    db: Session, nature: NatureManager, settings: Settings, *, include_terminated: bool = False
) -> GameSnapshot:
    """Monta o estado do mundo numa única passada pelo banco."""
    agents = agent_service.list_agents(db, include_terminated=include_terminated)
    placements = office_map.get_office_map().place_all(agents)
    sessions = _latest_sessions(db, agents)

    entries = tuple(
        _agent_entry(agent, placements.get(agent.id), sessions.get(agent.id), settings)
        for agent in agents
    )
    snapshot = nature.snapshot()
    resources = snapshot.to_dict()
    resources["queued_hirings"] = len(nature.pending())
    resources["active_subagents"] = sum(
        1
        for agent in agents
        if agent.agent_type is AgentType.SUBAGENT and agent.status is not AgentStatus.TERMINATED
    )
    resources["max_concurrent_subagents"] = settings.nature_max_concurrent_subagents

    return GameSnapshot(
        clock=office_map.corporate_clock(PROCESS_STARTED_AT),
        resources=resources,
        economy=_economy(db),
        agents=entries,
    )


def _latest_sessions(db: Session, agents: Sequence[Agent]) -> dict[uuid.UUID, ReasoningSession]:
    """Sessão de raciocínio mais recente por agente, em uma consulta só."""
    if not agents:
        return {}
    stmt = (
        select(ReasoningSession)
        .where(ReasoningSession.agent_id.in_([agent.id for agent in agents]))
        .order_by(ReasoningSession.started_at.desc(), ReasoningSession.id.desc())
        .limit(_RECENT_SESSION_WINDOW)
    )
    latest: dict[uuid.UUID, ReasoningSession] = {}
    for session in db.scalars(stmt):
        if session.agent_id is not None and session.agent_id not in latest:
            latest[session.agent_id] = session
    return latest


def chat_history(db: Session, *, limit: int = 200) -> list[dict[str, Any]]:
    """Falas recentes do log de comunicações, reconstruídas das sessões persistidas.

    Replica o que o frontend gera ao vivo: a tarefa de cada sessão, cada passo do
    raciocínio e o fracasso ou cancelamento. Devolve as `limit` falas mais recentes
    em ordem cronológica.
    """
    rows = db.execute(
        select(ReasoningSession, Agent.name)
        .outerjoin(Agent, Agent.id == ReasoningSession.agent_id)
        .order_by(ReasoningSession.started_at.desc(), ReasoningSession.id.desc())
        .limit(_CHAT_SESSION_WINDOW)
    ).all()
    if not rows:
        return []

    sessions_by_id: dict[uuid.UUID, tuple[ReasoningSession, str | None]] = {
        session.id: (session, agent_name) for session, agent_name in rows
    }
    messages: list[tuple[datetime, dict[str, Any]]] = []

    for session, agent_name in rows:
        speaker = {
            "agent_id": str(session.agent_id) if session.agent_id else None,
            "agent_name": agent_name or "Agente",
        }
        messages.append(
            (
                session.started_at,
                {
                    **speaker,
                    "id": f"task-{session.id}",
                    "kind": "TASK",
                    "text": session.task,
                    "at": session.started_at.isoformat(),
                },
            )
        )
        if session.status in _FAILED_STATUSES:
            ended_at = session.finished_at or session.started_at
            messages.append(
                (
                    ended_at,
                    {
                        **speaker,
                        "id": f"fail-{session.id}",
                        "kind": "SYSTEM",
                        "text": session.error or "Sessão encerrada sem conclusão.",
                        "at": ended_at.isoformat(),
                    },
                )
            )

    steps = db.execute(
        select(
            ReasoningStep.id,
            ReasoningStep.session_id,
            ReasoningStep.step_type,
            ReasoningStep.content,
            ReasoningStep.created_at,
        ).where(ReasoningStep.session_id.in_(list(sessions_by_id)))
    ).all()
    for step_id, session_id, step_type, content, created_at in steps:
        session, step_agent_name = sessions_by_id[session_id]
        messages.append(
            (
                created_at,
                {
                    "id": f"step-{step_id}",
                    "agent_id": str(session.agent_id) if session.agent_id else None,
                    "agent_name": step_agent_name or "Agente",
                    "kind": step_type.value,
                    "text": content,
                    "at": created_at.isoformat(),
                },
            )
        )

    messages.sort(key=lambda item: item[0])
    return [message for _, message in messages[-limit:]]


def _agent_entry(
    agent: Agent,
    placement: office_map.Placement | None,
    session: ReasoningSession | None,
    settings: Settings,
) -> dict[str, Any]:
    seat = office_map.seat_by_id(placement.seat_id) if placement and placement.seat_id else None
    return {
        "id": str(agent.id),
        "name": agent.name,
        "role": agent.role.value,
        "agent_type": agent.agent_type.value,
        "status": agent.status.value,
        "job_title": agent.job_title,
        "model_name": agent.model_name,
        "estimated_ram_mb": agent.estimated_ram_mb,
        "reports_to_id": str(agent.reports_to_id) if agent.reports_to_id else None,
        "created_at": agent.created_at.isoformat(),
        "activity": _activity(agent, session),
        "seat_id": placement.seat_id if placement else None,
        "room_id": seat.room_id if seat else None,
        "position": placement.to_dict() if placement else None,
        "reasoning": _reasoning_entry(session, settings),
    }


def _activity(agent: Agent, session: ReasoningSession | None) -> str:
    """O que o avatar deve estar fazendo no canvas."""
    if agent.status is AgentStatus.TERMINATED:
        return "TERMINATED"
    if session is not None and session.status is ReasoningStatus.RUNNING:
        return "THINKING"
    if agent.status is AgentStatus.WORKING:
        return "WORKING"
    if agent.status is AgentStatus.BLOCKED:
        return "BLOCKED"
    return "IDLE"


def _reasoning_entry(session: ReasoningSession | None, settings: Settings) -> dict[str, Any] | None:
    if session is None:
        return None
    max_steps = max(settings.reasoning_max_steps, 1)
    elapsed = (
        session.duration_ms
        if session.status is not ReasoningStatus.RUNNING and session.duration_ms
        else int((datetime.now(UTC) - session.started_at).total_seconds() * 1000)
    )
    return {
        "session_id": str(session.id),
        "status": session.status.value,
        "task": session.task,
        "model_name": session.model_name,
        "step_count": session.step_count,
        "total_tokens": session.total_tokens,
        "progress": round(min(session.step_count / max_steps, 1.0), 3),
        "elapsed_ms": elapsed,
        "conclusion": session.conclusion,
        "error": session.error,
        "started_at": session.started_at.isoformat(),
    }


def _economy(db: Session) -> dict[str, Any]:
    """Receita e custo corporativos derivados do consumo cognitivo."""
    sessions = list(db.scalars(select(ReasoningSession)))
    cost = round(sum(reasoning_metrics.cost_of(s) for s in sessions), 2)
    delivered = sum(1 for s in sessions if s.status is ReasoningStatus.COMPLETED)
    tokens = sum(s.total_tokens for s in sessions)
    return {
        "sessions": len(sessions),
        "delivered": delivered,
        "total_tokens": tokens,
        "cost_mb_s": cost,
        # Cada entrega concluída "fatura" os tokens que produziu; o ROI é a razão.
        "revenue_tokens": sum(
            s.total_tokens for s in sessions if s.status is ReasoningStatus.COMPLETED
        ),
        "roi": round(delivered / cost, 6) if cost else 0.0,
    }


def diff(previous: GameSnapshot | None, current: GameSnapshot) -> list[dict[str, Any]]:
    """Eventos derivados da comparação de dois snapshots consecutivos."""
    if previous is None:
        return []
    events: list[dict[str, Any]] = []
    before = {entry["id"]: entry for entry in previous.agents}
    after = {entry["id"]: entry for entry in current.agents}

    for agent_id, entry in after.items():
        if agent_id not in before:
            events.append({"event": "agent.joined", "agent_id": agent_id, "data": entry})
            continue
        old = before[agent_id]
        if old["activity"] != entry["activity"] or old["status"] != entry["status"]:
            events.append(
                {
                    "event": "agent.status",
                    "agent_id": agent_id,
                    "data": {
                        "activity": entry["activity"],
                        "status": entry["status"],
                        "model_name": entry["model_name"],
                        "reasoning": entry["reasoning"],
                    },
                }
            )
        if old["seat_id"] != entry["seat_id"] or old["position"] != entry["position"]:
            events.append(
                {"event": "agent.moved", "agent_id": agent_id, "data": entry["position"]}
            )

    for agent_id, entry in before.items():
        if agent_id not in after:
            events.append({"event": "agent.left", "agent_id": agent_id, "data": entry})

    if previous.resources["status"] != current.resources["status"]:
        events.append({"event": "nature.status", "agent_id": None, "data": current.resources})

    return events
