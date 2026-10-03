"""Banco de Talentos: perfis reutilizáveis de subagentes criados pelo RA."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, TimestampType, UUIDPrimaryKeyMixin
from app.models.enums import TaskComplexity


class TalentProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Metaprompt arquivado pelo RA para recontratação de um perfil recorrente."""

    __tablename__ = "talent_bank"
    __table_args__ = (UniqueConstraint("slug", name="uq_talent_bank_slug"),)

    slug: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(160), nullable=False)
    specialization: Mapped[str] = mapped_column(String(240), nullable=False, default="")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)

    tools: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    complexity: Mapped[TaskComplexity] = mapped_column(
        SAEnum(TaskComplexity, name="task_complexity"),
        nullable=False,
        default=TaskComplexity.SIMPLE,
    )
    recommended_model: Mapped[str | None] = mapped_column(String(120), nullable=True)

    usage_count: Mapped[int] = mapped_column(nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(TimestampType, nullable=True)
    created_by_role: Mapped[str] = mapped_column(String(32), nullable=False, default="RA")

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<TalentProfile {self.slug} usos={self.usage_count}>"
