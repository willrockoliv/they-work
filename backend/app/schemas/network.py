"""Schemas da rede corporativa — pedidos, tarefas, grafo e vereditos dos Chiefs."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AgentRole,
    ChiefDecision,
    CommunicationStatus,
    CommunicationType,
    InitialRequestStatus,
    TaskComplexity,
    TaskStatus,
)
from app.schemas.agents import AgentRead


class RequestActionCreate(BaseModel):
    """Pedido estratégico submetido pelo observador ao conselho."""

    topic: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3)
    submitted_by: str = Field(default="OBSERVER", max_length=120)
    #: Dispara deliberação do conselho na mesma requisição.
    auto_deliberate: bool = True


class BootstrapResponse(BaseModel):
    """Estado da fundação da empresa."""

    created: int
    total: int
    profiles: int
    chiefs: list[AgentRead] = Field(default_factory=list)

    @property
    def founded(self) -> bool:
        return self.total > 0


class InitialRequestRead(BaseModel):
    """Estado de um pedido na rede corporativa."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    description: str
    submitted_by: str
    status: InitialRequestStatus
    thread_id: uuid.UUID | None
    outcome: str | None
    narrative: str | None
    current_state: dict[str, Any]
    created_at: datetime
    resolved_at: datetime | None


class InitialRequestsResponse(BaseModel):
    total: int
    requests: list[InitialRequestRead] = Field(default_factory=list)


class AgentTaskRead(BaseModel):
    """Tarefa delegada por um Chief ao seu subordinado."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    parent_task_id: uuid.UUID | None
    assigned_by_chief_id: uuid.UUID | None
    assigned_to_agent_id: uuid.UUID | None
    title: str
    task_description: str
    context: dict[str, Any]
    status: TaskStatus
    attempt: int
    quality_score: int
    decision: ChiefDecision | None
    decision_rationale: str | None
    report_summary: str | None
    report_reasoning_session_id: uuid.UUID | None
    review_reasoning_session_id: uuid.UUID | None
    created_at: datetime
    delegated_at: datetime | None
    reported_at: datetime | None
    reviewed_at: datetime | None


class AgentTasksResponse(BaseModel):
    total: int
    tasks: list[AgentTaskRead] = Field(default_factory=list)


class CommunicationEdgeRead(BaseModel):
    """Aresta dirigida do grafo de comunicações."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    request_id: uuid.UUID
    task_id: uuid.UUID | None
    sender_agent_id: uuid.UUID | None
    recipient_agent_id: uuid.UUID | None
    communication_type: CommunicationType
    status: CommunicationStatus
    summary: str
    content: dict[str, Any]
    reasoning_session_id: uuid.UUID | None
    created_at: datetime


class GraphNode(BaseModel):
    """Nó do grafo: um agente ou o observador."""

    id: str
    name: str
    role: str
    agent_type: str
    status: str
    reports_to: str | None = None


class GraphEdge(BaseModel):
    """Aresta do grafo já pronta para desenho."""

    id: str
    request_id: str
    task_id: str | None = None
    sender_agent_id: str | None = None
    recipient_agent_id: str | None = None
    communication_type: CommunicationType
    status: CommunicationStatus
    summary: str
    content: dict[str, Any] = Field(default_factory=dict)
    reasoning_session_id: str | None = None
    created_at: str | None = None


class GraphTask(BaseModel):
    """Tarefa projetada dentro do grafo."""

    id: str
    request_id: str
    parent_task_id: str | None = None
    assigned_by_chief_id: str | None = None
    assigned_to_agent_id: str | None = None
    title: str
    task_description: str
    status: TaskStatus
    attempt: int
    quality_score: int
    decision: ChiefDecision | None = None
    decision_rationale: str | None = None
    report_summary: str | None = None
    report_reasoning_session_id: str | None = None
    review_reasoning_session_id: str | None = None


class RequestGraphResponse(BaseModel):
    """DAG completo de um pedido."""

    request_id: str
    topic: str
    status: InitialRequestStatus
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    tasks: list[GraphTask] = Field(default_factory=list)


class RequestDetailResponse(BaseModel):
    """Pedido com o grafo e as tarefas que ele gerou."""

    request: InitialRequestRead
    graph: RequestGraphResponse


class CreateAgentRequest(BaseModel):
    """Chief pede ao RA a criação de um agente especializado."""

    requesting_chief: AgentRole
    request_id: uuid.UUID
    job_title: str = Field(min_length=1, max_length=160)
    objective: str = ""
    specialization: str = Field(default="", max_length=240)
    deliverables: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    complexity: TaskComplexity | None = None


class CreateAgentResponse(BaseModel):
    """Resultado da criação: o agente já nasce reportando ao Chief solicitante."""

    hiring_request_id: uuid.UUID
    agent: AgentRead | None = None
    reporting_chief: AgentRole
    reused_profile: bool = False
    questions: list[str] = Field(default_factory=list)
    narrative: str = ""


class CreatedAgentsResponse(BaseModel):
    """Histórico dos agentes instanciados pelo RA."""

    total: int
    agents: list[AgentRead] = Field(default_factory=list)


class DelegateTaskRequest(BaseModel):
    """Tarefa que o Chief coloca na fila de um subordinado."""

    request_id: uuid.UUID
    agent_id: uuid.UUID
    title: str = Field(min_length=1, max_length=160)
    task_description: str = Field(min_length=3)
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class SupervisedAgentsResponse(BaseModel):
    """Time sob supervisão direta de um Chief."""

    total: int
    chief: AgentRole
    agents: list[AgentRead] = Field(default_factory=list)


class ReviewDecisionResponse(BaseModel):
    """Veredito do Chief sobre um report, com tudo o que ele desencadeou."""

    task: AgentTaskRead
    decision: ChiefDecision
    rationale: str
    quality_score: int
    achievement_ratio: float
    risk_level: str
    assessment: dict[str, Any] = Field(default_factory=dict)
    review_reasoning_session_id: uuid.UUID | None = None
    follow_up_task: AgentTaskRead | None = None
    consulted_roles: list[AgentRole] = Field(default_factory=list)
    escalated_to_ceo: bool = False


class RunCycleResponse(BaseModel):
    """Resultado de um ciclo automático completo sobre um pedido."""

    request: InitialRequestRead
    executed_tasks: int
    reviews: list[ReviewDecisionResponse] = Field(default_factory=list)
    graph: RequestGraphResponse


class StartCycleResponse(BaseModel):
    """Turno agendado para rodar em segundo plano."""

    request: InitialRequestRead
    #: `False` quando já havia um turno em andamento para este pedido.
    started: bool
