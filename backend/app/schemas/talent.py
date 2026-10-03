"""Schemas do Banco de Talentos."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TaskComplexity


class TalentProfileRead(BaseModel):
    """Perfil arquivado pelo RA."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    version: int
    is_active: bool
    supersedes_id: uuid.UUID | None
    role_title: str
    specialization: str
    system_prompt: str
    tools: dict[str, Any]
    keywords: dict[str, Any]
    complexity: TaskComplexity
    recommended_model: str | None
    usage_count: int
    rating_count: int
    average_rating: float | None
    last_used_at: datetime | None
    created_at: datetime


class TalentBankResponse(BaseModel):
    """Perfis disponíveis para recontratação."""

    total: int
    profiles: list[TalentProfileRead] = Field(default_factory=list)


class TalentSearchResponse(BaseModel):
    """Resultado da busca por um perfil reaproveitável."""

    found: bool
    matched_on: str | None = None
    score: float | None = None
    profile: TalentProfileRead | None = None


class TalentRatingRequest(BaseModel):
    """Avaliação de desempenho de um perfil, dada por um Chief."""

    rating: int = Field(ge=1, le=5)
    feedback: str | None = Field(default=None, max_length=1000)
