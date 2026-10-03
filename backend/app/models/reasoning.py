"""Observabilidade cognitiva — sessões ReAct e seus passos capturados.

Um `ReasoningSession` é uma execução de tarefa por um agente; cada `ReasoningStep`
é um nó do ciclo `Pensamento → Ação → Observação → Conclusão`, preservado na ordem
em que foi produzido para permitir replay e montagem do fluxograma.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    JSONType,
    TimestampMixin,
    TimestampType,
    UUIDPrimaryKeyMixin,
    UUIDType,
    utcnow,
)
from app.models.enums import ReasoningStatus, ReasoningStepType, TaskComplexity


class ReasoningSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Execução de uma tarefa por um agente, com o raciocínio integralmente capturado."""

    __tablename__ = "reasoning_sessions"
    __table_args__ = (
        Index("ix_reasoning_sessions_agent_started", "agent_id", "started_at"),
        Index("ix_reasoning_sessions_status", "status"),
    )

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    #: Correlaciona a sessão a uma deliberação do conselho, quando houver.
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    task: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReasoningStatus] = mapped_column(
        SAEnum(ReasoningStatus, name="reasoning_status"),
        nullable=False,
        default=ReasoningStatus.RUNNING,
    )
    complexity: Mapped[TaskComplexity] = mapped_column(
        SAEnum(TaskComplexity, name="task_complexity"),
        nullable=False,
        default=TaskComplexity.SIMPLE,
    )
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)

    step_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_ram_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conclusion: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime] = mapped_column(TimestampType, nullable=False, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    steps: Mapped[list[ReasoningStep]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ReasoningStep.sequence",
    )

    @property
    def is_running(self) -> bool:
        return self.status is ReasoningStatus.RUNNING

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<ReasoningSession {self.id} status={self.status.value} steps={self.step_count}>"


class ReasoningStep(Base, TimestampMixin):
    """Nó único do fluxo ReAct, imutável depois de gravado."""

    __tablename__ = "reasoning_steps"
    __table_args__ = (
        Index("ix_reasoning_steps_session_sequence", "session_id", "sequence"),
        Index("ix_reasoning_steps_type", "step_type"),
    )

    # SQLite só autoincrementa INTEGER; PostgreSQL recebe BIGINT.
    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer(), "sqlite"), primary_key=True, autoincrement=True
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reasoning_sessions.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[ReasoningStepType] = mapped_column(
        SAEnum(ReasoningStepType, name="reasoning_step_type"), nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    #: Contexto bruto da ferramenta: nome, entrada, resultado, erro, URLs, código.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    session: Mapped[ReasoningSession] = relationship(back_populates="steps")

    def to_dict(self) -> dict[str, Any]:
        """Representação transmitida por WebSocket e usada no fluxograma."""
        return {
            "id": self.id,
            "session_id": str(self.session_id),
            "sequence": self.sequence,
            "step_type": self.step_type.value,
            "content": self.content,
            "model_name": self.model_name,
            "tokens": self.tokens,
            "duration_ms": self.duration_ms,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<ReasoningStep #{self.sequence} {self.step_type.value}>"
