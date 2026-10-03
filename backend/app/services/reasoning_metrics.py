"""Métricas, retenção e export da trilha cognitiva.

O "custo" de um agente é medido na única moeda que existe neste sandbox: memória
ocupada ao longo do tempo (MB·s). O ROI compara as conclusões entregues com esse
custo — é o que permite ao conselho decidir se um subagente se pagou.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.models.agent import Agent
from app.models.base import utcnow
from app.models.enums import AuditEventType, ReasoningStatus, ReasoningStepType
from app.models.reasoning import ReasoningSession, ReasoningStep
from app.services import audit_service


@dataclass(frozen=True, slots=True)
class ReasoningMetrics:
    """Painel agregado da observabilidade cognitiva."""

    total_sessions: int
    completed: int
    failed: int
    running: int
    success_rate: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_duration_ms: float
    avg_steps: float
    cost_mb_s: float
    by_model: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    by_agent: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    by_step_type: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sessions": self.total_sessions,
            "completed": self.completed,
            "failed": self.failed,
            "running": self.running,
            "success_rate": self.success_rate,
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "avg_duration_ms": self.avg_duration_ms,
            "avg_steps": self.avg_steps,
            "cost_mb_s": self.cost_mb_s,
            "by_model": list(self.by_model),
            "by_agent": list(self.by_agent),
            "by_step_type": list(self.by_step_type),
        }


def cost_of(session: ReasoningSession) -> float:
    """Custo computacional em MB-segundo (RAM reservada vezes tempo de execução)."""
    return round(session.estimated_ram_mb * session.duration_ms / 1000, 2)


def collect(db: Session, *, since: datetime | None = None) -> ReasoningMetrics:
    """Consolida tokens, tempo, taxa de sucesso e ROI por agente e por modelo."""
    stmt = select(ReasoningSession)
    if since is not None:
        stmt = stmt.where(ReasoningSession.started_at >= since)
    sessions = list(db.scalars(stmt))

    completed = sum(1 for s in sessions if s.status is ReasoningStatus.COMPLETED)
    failed = sum(1 for s in sessions if s.status is ReasoningStatus.FAILED)
    running = sum(1 for s in sessions if s.status is ReasoningStatus.RUNNING)
    finished = completed + failed
    total = len(sessions)

    return ReasoningMetrics(
        total_sessions=total,
        completed=completed,
        failed=failed,
        running=running,
        success_rate=round(completed / finished, 4) if finished else 0.0,
        total_tokens=sum(s.total_tokens for s in sessions),
        prompt_tokens=sum(s.prompt_tokens for s in sessions),
        completion_tokens=sum(s.completion_tokens for s in sessions),
        avg_duration_ms=round(sum(s.duration_ms for s in sessions) / total, 2) if total else 0.0,
        avg_steps=round(sum(s.step_count for s in sessions) / total, 2) if total else 0.0,
        cost_mb_s=round(sum(cost_of(s) for s in sessions), 2),
        by_model=_group_by_model(sessions),
        by_agent=_group_by_agent(db, sessions),
        by_step_type=_group_by_step_type(db, since),
    )


def purge_sessions(
    db: Session, *, before: datetime | None = None, settings: Settings | None = None
) -> int:
    """Arquiva (remove) sessões anteriores ao corte de retenção. Deixa rastro na auditoria."""
    config = settings or get_settings()
    cutoff = before or utcnow() - timedelta(days=config.reasoning_retention_days)

    doomed = list(
        db.scalars(
            select(ReasoningSession.id).where(
                ReasoningSession.started_at < cutoff,
                ReasoningSession.status != ReasoningStatus.RUNNING,
            )
        )
    )
    if doomed:
        db.execute(delete(ReasoningStep).where(ReasoningStep.session_id.in_(doomed)))
        db.execute(delete(ReasoningSession).where(ReasoningSession.id.in_(doomed)))

    audit_service.record_event(
        db,
        event_type=AuditEventType.REASONING_PURGED,
        actor="SYSTEM",
        decision=str(len(doomed)),
        summary=f"Retenção cognitiva: {len(doomed)} sessão(ões) arquivada(s)",
        narrative=(
            f"A política de retenção de {config.reasoning_retention_days} dias removeu "
            f"{len(doomed)} sessão(ões) de raciocínio anteriores a {cutoff.isoformat()}."
        ),
        payload={"cutoff": cutoff.isoformat(), "removed": len(doomed)},
    )
    db.flush()
    return len(doomed)


def export_sessions(
    db: Session,
    *,
    agent_id: uuid.UUID | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Dump JSON de sessões com todos os passos, para análise fora do sandbox."""
    stmt = select(ReasoningSession).order_by(ReasoningSession.started_at.desc()).limit(limit)
    if agent_id is not None:
        stmt = stmt.where(ReasoningSession.agent_id == agent_id)
    if since is not None:
        stmt = stmt.where(ReasoningSession.started_at >= since)

    sessions = list(db.scalars(stmt))
    steps_by_session: dict[uuid.UUID, list[ReasoningStep]] = defaultdict(list)
    if sessions:
        ids = [s.id for s in sessions]
        rows = db.scalars(
            select(ReasoningStep)
            .where(ReasoningStep.session_id.in_(ids))
            .order_by(ReasoningStep.session_id, ReasoningStep.sequence)
        )
        for step in rows:
            steps_by_session[step.session_id].append(step)

    return [
        {
            "id": str(session.id),
            "agent_id": str(session.agent_id) if session.agent_id else None,
            "thread_id": str(session.thread_id) if session.thread_id else None,
            "task": session.task,
            "status": session.status.value,
            "complexity": session.complexity.value,
            "model_name": session.model_name,
            "step_count": session.step_count,
            "prompt_tokens": session.prompt_tokens,
            "completion_tokens": session.completion_tokens,
            "total_tokens": session.total_tokens,
            "duration_ms": session.duration_ms,
            "cost_mb_s": cost_of(session),
            "conclusion": session.conclusion,
            "error": session.error,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "finished_at": session.finished_at.isoformat() if session.finished_at else None,
            "steps": [step.to_dict() for step in steps_by_session[session.id]],
        }
        for session in sessions
    ]


# --- Agregações internas -----------------------------------------------------


def _group_by_model(sessions: list[ReasoningSession]) -> tuple[dict[str, Any], ...]:
    buckets: dict[str, list[ReasoningSession]] = defaultdict(list)
    for session in sessions:
        buckets[session.model_name or "desconhecido"].append(session)

    rows = [
        {
            "model": model,
            "sessions": len(group),
            "total_tokens": sum(s.total_tokens for s in group),
            "avg_duration_ms": round(sum(s.duration_ms for s in group) / len(group), 2),
        }
        for model, group in buckets.items()
    ]
    return tuple(sorted(rows, key=lambda row: row["sessions"], reverse=True))


def _group_by_agent(db: Session, sessions: list[ReasoningSession]) -> tuple[dict[str, Any], ...]:
    buckets: dict[uuid.UUID, list[ReasoningSession]] = defaultdict(list)
    for session in sessions:
        if session.agent_id is not None:
            buckets[session.agent_id].append(session)
    if not buckets:
        return ()

    agents = {
        agent.id: agent
        for agent in db.scalars(select(Agent).where(Agent.id.in_(list(buckets))))
    }
    rows: list[dict[str, Any]] = []
    for agent_id, group in buckets.items():
        agent = agents.get(agent_id)
        cost = sum(cost_of(s) for s in group)
        delivered = sum(1 for s in group if s.status is ReasoningStatus.COMPLETED)
        rows.append(
            {
                "agent_id": str(agent_id),
                "name": agent.name if agent else "desconhecido",
                "role": agent.role.value if agent else None,
                "sessions": len(group),
                "completed": delivered,
                "total_tokens": sum(s.total_tokens for s in group),
                "avg_duration_ms": round(sum(s.duration_ms for s in group) / len(group), 2),
                "cost_mb_s": round(cost, 2),
                # Conclusões entregues por MB·s consumido.
                "roi": round(delivered / cost, 6) if cost else 0.0,
            }
        )
    return tuple(sorted(rows, key=lambda row: row["sessions"], reverse=True))


def _group_by_step_type(db: Session, since: datetime | None) -> tuple[dict[str, Any], ...]:
    stmt = select(
        ReasoningStep.step_type,
        func.count(ReasoningStep.id),
        func.coalesce(func.sum(ReasoningStep.tokens), 0),
        func.coalesce(func.avg(ReasoningStep.duration_ms), 0.0),
    ).group_by(ReasoningStep.step_type)
    if since is not None:
        stmt = stmt.join(ReasoningSession).where(ReasoningSession.started_at >= since)

    rows = {
        step_type: {
            "step_type": step_type.value,
            "count": int(count),
            "total_tokens": int(tokens),
            "avg_duration_ms": round(float(avg_duration), 2),
        }
        for step_type, count, tokens, avg_duration in db.execute(stmt)
    }
    return tuple(
        rows.get(
            step_type,
            {
                "step_type": step_type.value,
                "count": 0,
                "total_tokens": 0,
                "avg_duration_ms": 0.0,
            },
        )
        for step_type in ReasoningStepType
    )
