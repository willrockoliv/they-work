"""Schemas de agentes."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgentRole, AgentStatus, AgentType


class AgentRead(BaseModel):
    """Representação pública de um agente."""

    model_config = ConfigDict(from_attributes=True)

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
    terminated_at: datetime | None


class ChiefsInitResponse(BaseModel):
    """Resultado da inicialização do conselho administrativo."""

    created: int
    total: int
    chiefs: list[AgentRead] = Field(default_factory=list)


class AgentsStatusResponse(BaseModel):
    """Panorama de todos os agentes vivos."""

    total: int
    chiefs: list[AgentRead] = Field(default_factory=list)
    subagents: list[AgentRead] = Field(default_factory=list)
