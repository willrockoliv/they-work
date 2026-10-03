"""Agentes da empresa: Chiefs fixos e subagentes efêmeros."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, JSONType, TimestampMixin, TimestampType, UUIDPrimaryKeyMixin
from app.models.enums import AgentRole, AgentStatus, AgentType


class Agent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Um colaborador da empresa virtual (Chief fixo ou subagente temporário)."""

    __tablename__ = "agents"
    __table_args__ = (
        Index("ix_agents_type_status", "agent_type", "status"),
        Index("ix_agents_role", "role"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[AgentRole] = mapped_column(SAEnum(AgentRole, name="agent_role"), nullable=False)
    agent_type: Mapped[AgentType] = mapped_column(
        SAEnum(AgentType, name="agent_type"), nullable=False
    )
    status: Mapped[AgentStatus] = mapped_column(
        SAEnum(AgentStatus, name="agent_status"), nullable=False, default=AgentStatus.IDLE
    )

    job_title: Mapped[str | None] = mapped_column(String(160), nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    estimated_ram_mb: Mapped[int] = mapped_column(nullable=False, default=0)

    reports_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    talent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("talent_bank.id", ondelete="SET NULL"), nullable=True
    )

    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    terminated_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    reports_to: Mapped[Agent | None] = relationship(
        remote_side="Agent.id", back_populates="subordinates"
    )
    subordinates: Mapped[list[Agent]] = relationship(back_populates="reports_to")

    @property
    def is_chief(self) -> bool:
        return self.agent_type is AgentType.CHIEF

    @property
    def is_active(self) -> bool:
        return self.status is not AgentStatus.TERMINATED

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<Agent {self.role.value}:{self.name} status={self.status.value}>"
