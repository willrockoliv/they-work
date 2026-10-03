"""Contratos da API de observabilidade cognitiva (Fase 3)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ReasoningStatus, ReasoningStepType, TaskComplexity


class ReasoningStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sequence: int
    step_type: ReasoningStepType
    content: str
    model_name: str | None = None
    tokens: int = 0
    duration_ms: int = 0
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReasoningSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID | None = None
    thread_id: uuid.UUID | None = None
    task: str
    status: ReasoningStatus
    complexity: TaskComplexity
    model_name: str | None = None
    step_count: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int
    conclusion: str | None = None
    error: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class ReasoningSessionDetail(ReasoningSessionRead):
    steps: list[ReasoningStepRead] = Field(default_factory=list)


class ReasoningSessionsResponse(BaseModel):
    total: int
    sessions: list[ReasoningSessionRead] = Field(default_factory=list)


class ReasoningRunRequest(BaseModel):
    task: str = Field(min_length=3)
    complexity: TaskComplexity | None = None
    thread_id: uuid.UUID | None = None
    max_steps: int | None = Field(default=None, gt=0, le=32)
    context: dict[str, Any] = Field(default_factory=dict)


class ReasoningFlowNode(BaseModel):
    id: str
    type: str
    label: str
    content: str
    icon: str
    color: str
    column: int
    row: int
    payload: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)


class ReasoningFlowEdge(BaseModel):
    id: str
    source: str
    target: str
    kind: str
    label: str


class ReasoningFlowResponse(BaseModel):
    nodes: list[ReasoningFlowNode] = Field(default_factory=list)
    edges: list[ReasoningFlowEdge] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class LiveStatusResponse(BaseModel):
    agent_id: uuid.UUID
    agent_name: str
    agent_status: str
    model_name: str | None = None
    session_id: uuid.UUID | None = None
    reasoning_status: ReasoningStatus | None = None
    task: str | None = None
    step_count: int = 0
    progress: float = 0.0
    last_step_type: ReasoningStepType | None = None
    last_action: str | None = None
    elapsed_ms: int = 0
    started_at: datetime | None = None
    conclusion: str | None = None
    error: str | None = None


class ReasoningMetricsResponse(BaseModel):
    total_sessions: int
    completed: int
    failed: int
    running: int
    success_rate: float
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_duration_ms: float
    avg_steps: float
    cost_mb_s: float
    by_model: list[dict[str, Any]] = Field(default_factory=list)
    by_agent: list[dict[str, Any]] = Field(default_factory=list)
    by_step_type: list[dict[str, Any]] = Field(default_factory=list)


class RetentionPurgeRequest(BaseModel):
    before: datetime | None = None


class RetentionPurgeResponse(BaseModel):
    removed: int
    retention_days: int


class ReasoningExportResponse(BaseModel):
    total: int
    sessions: list[dict[str, Any]] = Field(default_factory=list)
