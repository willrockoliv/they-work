"""Schemas do conselho administrativo (personas C-Level)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AgentRole,
    CommunicationKind,
    CouncilOutcome,
    CouncilStance,
    TaskComplexity,
)


class ChiefProfileRead(BaseModel):
    """Perfil cognitivo persistido de um Chief."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: AgentRole
    agent_id: uuid.UUID | None
    headline: str
    mission: str
    reasoning_style: str
    objectives: dict[str, Any]
    decision_criteria: dict[str, Any]
    context_memory: dict[str, Any]
    priority: int
    default_complexity: TaskComplexity


class ChiefProfilesResponse(BaseModel):
    """Conselho completo."""

    total: int
    profiles: list[ChiefProfileRead] = Field(default_factory=list)


class ChiefOpinionRead(BaseModel):
    """Parecer individual de um Chief."""

    role: AgentRole
    stance: CouncilStance
    confidence: int
    rationale: str
    concerns: list[str] = Field(default_factory=list)


class DeliberationRequest(BaseModel):
    """Proposta submetida ao conselho."""

    topic: str = Field(min_length=3, max_length=255)
    description: str = Field(min_length=3)
    submitted_by: AgentRole = AgentRole.CEO
    context: dict[str, Any] = Field(default_factory=dict)


class DeliberationResponse(BaseModel):
    """Veredito consolidado pelo CEO."""

    thread_id: uuid.UUID
    topic: str
    outcome: CouncilOutcome
    complexity: TaskComplexity
    narrative: str
    conditions: list[str] = Field(default_factory=list)
    opinions: list[ChiefOpinionRead] = Field(default_factory=list)


class CommunicationRead(BaseModel):
    """Uma fala registrada do conselho."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    kind: CommunicationKind
    from_role: AgentRole
    to_role: AgentRole | None
    topic: str
    content: str
    rationale: str | None
    verdict: str | None
    confidence: int
    created_at: datetime


class CommunicationsResponse(BaseModel):
    """Histórico de comunicações do conselho."""

    total: int
    communications: list[CommunicationRead] = Field(default_factory=list)


class MemoryFactRequest(BaseModel):
    """Fato a ser gravado na memória de contexto de um Chief."""

    fact: str = Field(min_length=3, max_length=1000)
    importance: int = Field(default=5, ge=1, le=10)
