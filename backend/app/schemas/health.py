"""Schemas do health check."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

HealthState = Literal["ok", "degraded", "down"]


class ComponentHealth(BaseModel):
    """Estado de uma dependência externa."""

    name: str
    status: HealthState
    detail: str | None = None


class HealthResponse(BaseModel):
    """Resposta do endpoint `/health`."""

    status: HealthState
    app_name: str
    version: str
    environment: str
    timestamp: datetime
    components: list[ComponentHealth] = Field(default_factory=list)
