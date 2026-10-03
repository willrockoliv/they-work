"""Consultas sobre a trilha cognitiva — histórico, replay e sessão corrente."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ReasoningStatus
from app.models.reasoning import ReasoningSession, ReasoningStep


def get_session(db: Session, session_id: uuid.UUID) -> ReasoningSession | None:
    return db.get(ReasoningSession, session_id)


def list_sessions(
    db: Session,
    *,
    agent_id: uuid.UUID | None = None,
    status: ReasoningStatus | None = None,
    limit: int = 50,
) -> list[ReasoningSession]:
    """Sessões mais recentes, opcionalmente filtradas por agente e estado."""
    stmt = select(ReasoningSession).order_by(ReasoningSession.started_at.desc()).limit(limit)
    if agent_id is not None:
        stmt = stmt.where(ReasoningSession.agent_id == agent_id)
    if status is not None:
        stmt = stmt.where(ReasoningSession.status == status)
    return list(db.scalars(stmt))


def latest_for_agent(db: Session, agent_id: uuid.UUID) -> ReasoningSession | None:
    """Sessão em execução do agente ou, na falta dela, a última encerrada."""
    running = db.scalars(
        select(ReasoningSession)
        .where(
            ReasoningSession.agent_id == agent_id,
            ReasoningSession.status == ReasoningStatus.RUNNING,
        )
        .order_by(ReasoningSession.started_at.desc())
        .limit(1)
    ).first()
    if running is not None:
        return running
    return db.scalars(
        select(ReasoningSession)
        .where(ReasoningSession.agent_id == agent_id)
        .order_by(ReasoningSession.started_at.desc())
        .limit(1)
    ).first()


def list_steps(db: Session, session_id: uuid.UUID) -> list[ReasoningStep]:
    """Passos de uma sessão na ordem em que foram produzidos."""
    return list(
        db.scalars(
            select(ReasoningStep)
            .where(ReasoningStep.session_id == session_id)
            .order_by(ReasoningStep.sequence)
        )
    )
