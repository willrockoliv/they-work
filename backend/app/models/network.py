"""Rede corporativa — pedidos do observador, tarefas delegadas e o grafo de comunicações.

O fluxo da Fase 5 é um DAG, não um pipeline: cada pedido (`InitialRequest`) gera
tarefas (`AgentTask`) delegadas por um Chief ao seu time, e toda troca entre agentes
vira uma aresta (`CommunicationEdge`) com o raciocínio que a originou anexado.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    JSONType,
    TimestampMixin,
    TimestampType,
    UUIDPrimaryKeyMixin,
    UUIDType,
)
from app.models.enums import (
    ChiefDecision,
    CommunicationStatus,
    CommunicationType,
    InitialRequestStatus,
    TaskStatus,
)


class InitialRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Pedido estratégico submetido pelo observador e endereçado ao conselho."""

    __tablename__ = "initial_requests"
    __table_args__ = (Index("ix_initial_requests_status_created", "status", "created_at"),)

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_by: Mapped[str] = mapped_column(String(120), nullable=False, default="OBSERVER")

    status: Mapped[InitialRequestStatus] = mapped_column(
        SAEnum(InitialRequestStatus, name="initial_request_status"),
        nullable=False,
        default=InitialRequestStatus.PROPOSED,
    )
    #: Correlaciona o pedido à thread de deliberação do conselho.
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUIDType, nullable=True)

    outcome: Mapped[str | None] = mapped_column(String(64), nullable=True)
    narrative: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Snapshots sucessivos do progresso, acumulados a cada mutação do grafo.
    current_state: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    resolved_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    tasks: Mapped[list[AgentTask]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<InitialRequest {self.topic[:32]} status={self.status.value}>"


class AgentTask(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Tarefa delegada por um Chief supervisor a um agente do seu próprio time."""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index("ix_agent_tasks_request_status", "request_id", "status"),
        Index("ix_agent_tasks_assignee_status", "assigned_to_agent_id", "status"),
        Index("ix_agent_tasks_chief_status", "assigned_by_chief_id", "status"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("initial_requests.id", ondelete="CASCADE"), nullable=False
    )
    #: Subtarefa criada por um veredito MODIFY aponta para a tarefa original.
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )

    assigned_by_chief_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(160), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    status: Mapped[TaskStatus] = mapped_column(
        SAEnum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.PENDING
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    report_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_reasoning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reasoning_sessions.id", ondelete="SET NULL"), nullable=True
    )
    review_reasoning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reasoning_sessions.id", ondelete="SET NULL"), nullable=True
    )

    quality_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decision: Mapped[ChiefDecision | None] = mapped_column(
        SAEnum(ChiefDecision, name="chief_decision"), nullable=True
    )
    decision_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    delegated_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    reported_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    request: Mapped[InitialRequest] = relationship(back_populates="tasks")

    @property
    def is_open(self) -> bool:
        return self.status not in (
            TaskStatus.COMPLETED,
            TaskStatus.REJECTED,
            TaskStatus.CANCELLED,
        )

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<AgentTask {self.title[:32]} status={self.status.value} attempt={self.attempt}>"


class CommunicationEdge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Aresta dirigida do grafo: quem falou com quem, sobre o quê e por quê."""

    __tablename__ = "communication_graph"
    __table_args__ = (
        Index("ix_communication_graph_request_created", "request_id", "created_at"),
        Index("ix_communication_graph_type", "communication_type"),
    )

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("initial_requests.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True
    )

    #: Nulo no emissor significa o observador humano; no destinatário, todo o conselho.
    sender_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    recipient_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )

    communication_type: Mapped[CommunicationType] = mapped_column(
        SAEnum(CommunicationType, name="communication_type"), nullable=False
    )
    status: Mapped[CommunicationStatus] = mapped_column(
        SAEnum(CommunicationStatus, name="communication_status"),
        nullable=False,
        default=CommunicationStatus.PENDING,
    )

    summary: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    reasoning_session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("reasoning_sessions.id", ondelete="SET NULL"), nullable=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)

    def to_dict(self) -> dict[str, Any]:
        """Representação da aresta transmitida ao frontend."""
        return {
            "id": str(self.id),
            "request_id": str(self.request_id),
            "task_id": str(self.task_id) if self.task_id else None,
            "sender_agent_id": str(self.sender_agent_id) if self.sender_agent_id else None,
            "recipient_agent_id": (
                str(self.recipient_agent_id) if self.recipient_agent_id else None
            ),
            "communication_type": self.communication_type.value,
            "status": self.status.value,
            "summary": self.summary,
            "content": self.content,
            "reasoning_session_id": (
                str(self.reasoning_session_id) if self.reasoning_session_id else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<CommunicationEdge {self.communication_type.value}:{self.summary[:32]}>"
