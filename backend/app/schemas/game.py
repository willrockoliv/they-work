"""Schemas do mundo 2D (Fase 4)."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import AgentRole, AgentStatus, AgentType, ReasoningStatus
from app.schemas.resources import ResourceStatusResponse


class RoomRead(BaseModel):
    """Cômodo do escritório, em coordenadas de tile."""

    id: str
    label: str
    kind: str
    x: int
    y: int
    width: int
    height: int


class SeatRead(BaseModel):
    """Posto de trabalho fixo."""

    id: str
    kind: str
    room_id: str
    x: int
    y: int
    index: int
    role: AgentRole | None = None


class HotspotRead(BaseModel):
    """Ponto de interesse clicável (centro de um cômodo)."""

    id: str
    room_id: str
    label: str
    x: float
    y: float


class OfficeLayoutResponse(BaseModel):
    """Planta do escritório — estática durante toda a simulação."""

    tile_size: int
    columns: int
    rows: int
    rooms: list[RoomRead] = Field(default_factory=list)
    seats: list[SeatRead] = Field(default_factory=list)
    hotspots: list[HotspotRead] = Field(default_factory=list)


class PositionRead(BaseModel):
    """Posição corrente e destino de um agente, em tiles."""

    agent_id: uuid.UUID
    seat_id: str | None
    x: float
    y: float
    target_x: float
    target_y: float
    manual: bool


class AgentReasoningRead(BaseModel):
    """Resumo da sessão cognitiva corrente do agente."""

    session_id: uuid.UUID
    status: ReasoningStatus
    task: str
    model_name: str | None
    step_count: int
    total_tokens: int
    progress: float
    elapsed_ms: int
    conclusion: str | None
    error: str | None
    started_at: datetime


class GameAgentRead(BaseModel):
    """Agente como o canvas precisa enxergá-lo."""

    id: uuid.UUID
    name: str
    role: AgentRole
    agent_type: AgentType
    status: AgentStatus
    job_title: str | None
    model_name: str | None
    estimated_ram_mb: int
    reports_to_id: uuid.UUID | None
    created_at: datetime
    activity: str
    seat_id: str | None
    room_id: str | None
    position: PositionRead | None
    reasoning: AgentReasoningRead | None


class GameClockRead(BaseModel):
    """Relógio corporativo simulado."""

    day: int
    hour: int
    minute: int
    label: str
    elapsed_seconds: float


class GameEconomyRead(BaseModel):
    """Receita e custo corporativos derivados do consumo cognitivo."""

    sessions: int
    delivered: int
    total_tokens: int
    cost_mb_s: float
    revenue_tokens: int
    roi: float


class GameStateResponse(BaseModel):
    """Estado completo do mundo 2D."""

    clock: GameClockRead
    resources: ResourceStatusResponse
    economy: GameEconomyRead
    layout: OfficeLayoutResponse
    agents: list[GameAgentRead] = Field(default_factory=list)


class MoveRequest(BaseModel):
    """Destino de um agente no grid do escritório."""

    x: float = Field(ge=0)
    y: float = Field(ge=0)


class ChatHistoryMessage(BaseModel):
    """Fala do log de comunicações, no mesmo formato do feed ao vivo."""

    id: str
    agent_id: str | None
    agent_name: str
    kind: str
    text: str
    at: str


class ChatHistoryResponse(BaseModel):
    """Falas recentes em ordem cronológica."""

    messages: list[ChatHistoryMessage] = Field(default_factory=list)
