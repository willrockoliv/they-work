"""Trilha de auditoria — decisões da Natureza e eventos do ciclo de vida dos agentes."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin
from app.models.enums import AuditEventType


class AuditLog(Base, TimestampMixin):
    """Registro imutável de uma ação relevante do ecossistema."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_event_created", "event_type", "created_at"),
        Index("ix_audit_logs_actor", "actor"),
    )

    # SQLite só autoincrementa INTEGER; PostgreSQL recebe BIGINT.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType, name="audit_event_type"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(64), nullable=False, default="SYSTEM")
    decision: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str] = mapped_column(String(255), nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    resource_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<AuditLog {self.event_type.value} actor={self.actor}>"
