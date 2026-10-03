"""Registro da trilha de auditoria corporativa."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.enums import AuditEventType


def record_event(
    session: Session,
    *,
    event_type: AuditEventType,
    summary: str,
    actor: str = "SYSTEM",
    decision: str | None = None,
    narrative: str | None = None,
    agent_id: uuid.UUID | None = None,
    resource_snapshot: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> AuditLog:
    """Persiste um evento de auditoria (sem commit — cabe ao chamador)."""
    entry = AuditLog(
        event_type=event_type,
        summary=summary[:255],
        actor=actor,
        decision=decision,
        narrative=narrative,
        agent_id=agent_id,
        resource_snapshot=resource_snapshot or {},
        payload=payload or {},
    )
    session.add(entry)
    return entry


def list_events(
    session: Session,
    *,
    event_type: AuditEventType | None = None,
    limit: int = 50,
) -> list[AuditLog]:
    """Eventos mais recentes, opcionalmente filtrados por tipo."""
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
    if event_type is not None:
        stmt = stmt.where(AuditLog.event_type == event_type)
    return list(session.scalars(stmt))
