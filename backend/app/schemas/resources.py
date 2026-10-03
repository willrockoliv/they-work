"""Schemas de recursos e das decisões da Natureza."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import NatureDecision, ResourceStatus, TaskComplexity


class ResourceStatusResponse(BaseModel):
    """Fotografia dos recursos físicos monitorados pela Natureza."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    status: ResourceStatus
    narrative: str

    ram_limit_mb: int
    ram_total_mb: int
    ram_used_mb: int
    ram_allocatable_mb: int
    ram_usage_ratio: float

    vram_limit_mb: int
    vram_total_mb: int
    vram_used_mb: int
    vram_allocatable_mb: int
    vram_usage_ratio: float

    gpu_detected: bool
    cpu_percent: float

    queued_hirings: int = 0
    active_subagents: int = 0
    max_concurrent_subagents: int = 0


class HiringEvaluationRequest(BaseModel):
    """Requisição de contratação submetida à Natureza."""

    requested_by: str = Field(min_length=2, max_length=32, examples=["CTO"])
    job_title: str = Field(min_length=2, max_length=160, examples=["Analista de Dados"])
    complexity: TaskComplexity = TaskComplexity.SIMPLE
    requested_model: str | None = Field(default=None, examples=["qwen3:8b"])


class HiringVerdictResponse(BaseModel):
    """Veredito da Natureza sobre a contratação."""

    decision: NatureDecision
    allowed: bool
    requested_by: str
    job_title: str
    complexity: TaskComplexity
    requested_model: str | None
    granted_model: str | None
    reason: str
    narrative: str
    queue_position: int | None
    resources: ResourceStatusResponse
