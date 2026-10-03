"""Requisições de contratação de subagentes abertas pelos Chiefs ao RA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, TimestampType, UUIDPrimaryKeyMixin
from app.models.enums import AgentRole, NatureDecision, RequestStatus, TaskComplexity


class SubagentRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pedido de um Chief ao RA, com o rastro completo até a contratação ou recusa."""

    __tablename__ = "subagent_requests"
    __table_args__ = (
        Index("ix_subagent_requests_status_created", "status", "created_at"),
        Index("ix_subagent_requests_requested_by", "requested_by_role"),
    )

    requested_by_role: Mapped[AgentRole] = mapped_column(
        SAEnum(AgentRole, name="agent_role"), nullable=False
    )
    requester_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False, default="")
    raw_request: Mapped[str] = mapped_column(Text, nullable=False, default="")

    deliverables: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    tools: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    constraints: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    complexity: Mapped[TaskComplexity] = mapped_column(
        SAEnum(TaskComplexity, name="task_complexity"),
        nullable=False,
        default=TaskComplexity.SIMPLE,
    )
    requested_model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    status: Mapped[RequestStatus] = mapped_column(
        SAEnum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.DRAFT
    )
    clarifications: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    nature_decision: Mapped[NatureDecision | None] = mapped_column(
        SAEnum(NatureDecision, name="nature_decision"), nullable=True
    )
    nature_narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    queue_position: Mapped[int | None] = mapped_column(nullable=True)

    talent_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("talent_bank.id", ondelete="SET NULL"), nullable=True
    )
    reused_profile: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    @property
    def is_open(self) -> bool:
        return self.status in (
            RequestStatus.DRAFT,
            RequestStatus.NEEDS_CLARIFICATION,
            RequestStatus.CLARIFIED,
            RequestStatus.QUEUED,
        )

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<SubagentRequest {self.job_title} status={self.status.value}>"
