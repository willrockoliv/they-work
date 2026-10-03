"""Banco de Talentos: perfis reutilizáveis de subagentes criados pelo RA."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, TimestampType, UUIDPrimaryKeyMixin
from app.models.enums import TaskComplexity


class TalentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metaprompt arquivado pelo RA para recontratação de um perfil recorrente."""

    __tablename__ = "talent_bank"
    __table_args__ = (
        UniqueConstraint("slug", "version", name="uq_talent_bank_slug_version"),
        Index("ix_talent_bank_slug_active", "slug", "is_active"),
    )

    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("talent_bank.id", ondelete="SET NULL"), nullable=True
    )

    role_title: Mapped[str] = mapped_column(String(160), nullable=False)
    specialization: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    tools: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    # Termos normalizados usados na busca por perfis recorrentes.
    keywords: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    complexity: Mapped[TaskComplexity] = mapped_column(
        SAEnum(TaskComplexity, name="task_complexity"),
        nullable=False,
        default=TaskComplexity.SIMPLE,
    )
    recommended_model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    created_by_role: Mapped[str] = mapped_column(String(32), nullable=False, default="RA")

    rating_sum: Mapped[int] = mapped_column(nullable=False, default=0)
    rating_count: Mapped[int] = mapped_column(nullable=False, default=0)
    task_history: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    @property
    def average_rating(self) -> float | None:
        """Nota média (1 a 5) atribuída pelos Chiefs, ou `None` se nunca avaliado."""
        if self.rating_count == 0:
            return None
        return round(self.rating_sum / self.rating_count, 2)

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<TalentProfile {self.slug}@v{self.version} usos={self.usage_count}>"
