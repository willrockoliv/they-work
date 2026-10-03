"""Schemas do fluxo de contratação conduzido pelo RA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AgentRole, NatureDecision, RequestStatus, TaskComplexity
from app.schemas.agents import AgentRead
from app.schemas.resources import ResourceStatusResponse


class SubagentRequestCreate(BaseModel):
    """Requisição de contratação aberta por um Chief."""

    requested_by: AgentRole
    job_title: str = Field(min_length=1, max_length=160)
    objective: str = ""
    raw_request: str = ""
    specialization: str = Field(default="", max_length=240)
    deliverables: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    complexity: TaskComplexity | None = None
    requested_model: str | None = None


class ClarificationRequest(BaseModel):
    """Respostas do Chief às perguntas do RA."""

    job_title: str | None = Field(default=None, max_length=160)
    objective: str | None = None
    specialization: str | None = Field(default=None, max_length=240)
    deliverables: list[str] | None = None
    tools: list[str] | None = None


class SubagentRequestRead(BaseModel):
    """Estado de uma requisição no pipeline do RA."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requested_by_role: AgentRole
    job_title: str
    objective: str
    status: RequestStatus
    complexity: TaskComplexity
    requested_model: str | None
    granted_model: str | None
    nature_decision: NatureDecision | None
    nature_narrative: str | None
    queue_position: int | None
    talent_profile_id: uuid.UUID | None
    reused_profile: bool
    created_agent_id: uuid.UUID | None
    clarifications: dict[str, Any]
    created_at: datetime
    resolved_at: datetime | None


class HiringOutcomeResponse(BaseModel):
    """Resultado do pipeline: contratado, questionado, enfileirado ou barrado."""

    request: SubagentRequestRead
    agent: AgentRead | None = None
    questions: list[str] = Field(default_factory=list)
    reused_profile: bool = False
    narrative: str = ""
    resources: ResourceStatusResponse | None = None


class SubagentRequestsResponse(BaseModel):
    """Lista de requisições."""

    total: int
    requests: list[SubagentRequestRead] = Field(default_factory=list)


class DismissalRequest(BaseModel):
    """Demissão de um subagente ao fim da sprint."""

    reason: str = Field(min_length=3, max_length=500)
    final_report: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
