"""Schemas do catálogo de modelos Ollama."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import TaskComplexity


class ModelAvailability(BaseModel):
    """Ficha técnica de um modelo somada à sua disponibilidade local."""

    name: str
    display_name: str
    vendor: str
    parameters: str
    quantization: str
    ram_mb: int
    vram_mb: int
    tier: int
    max_complexity: TaskComplexity
    strengths: list[str] = Field(default_factory=list)
    installed: bool = False
    installed_size_mb: int | None = None
    fits_current_budget: bool = False


class ModelsAvailableResponse(BaseModel):
    """Resposta de `/models/available`."""

    ollama_reachable: bool
    ollama_version: str | None = None
    ram_allocatable_mb: int
    models: list[ModelAvailability] = Field(default_factory=list)


class ModelSelectionResponse(BaseModel):
    """Modelo escolhido para uma complexidade de tarefa, já ajustado pela Natureza."""

    complexity: TaskComplexity
    preferred_model: str
    selected_model: str | None
    downgraded: bool
    reason: str
    ram_allocatable_mb: int
