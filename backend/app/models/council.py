"""Conselho administrativo: perfis das personas C-Level e suas comunicações."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin, UUIDType
from app.models.enums import AgentRole, CommunicationKind, TaskComplexity


class ChiefProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Perfil cognitivo persistido de um Chief: missão, objetivos e critérios de decisão."""

    __tablename__ = "chief_profiles"
    __table_args__ = (UniqueConstraint("role", name="uq_chief_profiles_role"),)

    role: Mapped[AgentRole] = mapped_column(SAEnum(AgentRole, name="agent_role"), nullable=False)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    headline: Mapped[str] = mapped_column(String(160), nullable=False)
    mission: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning_style: Mapped[str] = mapped_column(Text, nullable=False, default="")

    objectives: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    decision_criteria: Mapped[dict[str, Any]] = mapped_column(
        JSONType, nullable=False, default=dict
    )
    # Fatos corporativos acumulados que entram no contexto do Chief a cada deliberação.
    context_memory: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    priority: Mapped[int] = mapped_column(nullable=False, default=5)
    default_complexity: Mapped[TaskComplexity] = mapped_column(
        SAEnum(TaskComplexity, name="task_complexity"),
        nullable=False,
        default=TaskComplexity.MODERATE,
    )

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<ChiefProfile {self.role.value}>"


class ChiefCommunication(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Registro imutável de uma fala, análise ou decisão do conselho."""

    __tablename__ = "chief_communications"
    __table_args__ = (
        Index("ix_chief_communications_thread", "thread_id", "created_at"),
        Index("ix_chief_communications_from_kind", "from_role", "kind"),
    )

    thread_id: Mapped[uuid.UUID] = mapped_column(UUIDType, nullable=False, default=uuid.uuid4)
    kind: Mapped[CommunicationKind] = mapped_column(
        SAEnum(CommunicationKind, name="communication_kind"), nullable=False
    )

    from_role: Mapped[AgentRole] = mapped_column(
        SAEnum(AgentRole, name="agent_role"), nullable=False
    )
    # Nulo significa comunicado para todo o conselho.
    to_role: Mapped[AgentRole | None] = mapped_column(
        SAEnum(AgentRole, name="agent_role"), nullable=True
    )

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    verdict: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confidence: Mapped[int] = mapped_column(nullable=False, default=5)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<ChiefCommunication {self.from_role.value}->{self.kind.value}:{self.topic[:32]}>"
