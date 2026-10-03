"""Memória corporativa de longo prazo da empresa virtual."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, JSONType, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MemoryType


class CorporateMemory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Decisões, relatórios e conhecimento preservados após a demissão dos subagentes."""

    __tablename__ = "corporate_memory"
    __table_args__ = (
        Index("ix_corporate_memory_type_created", "memory_type", "created_at"),
        Index("ix_corporate_memory_importance", "importance"),
    )

    memory_type: Mapped[MemoryType] = mapped_column(
        SAEnum(MemoryType, name="memory_type"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    author_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True
    )
    author_role: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # 1 = anotação trivial, 10 = decisão fundadora da empresa.
    importance: Mapped[int] = mapped_column(nullable=False, default=5)
    tags: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)

    def __repr__(self) -> str:  # pragma: no cover - auxílio de depuração
        return f"<CorporateMemory {self.memory_type.value}:{self.title[:32]}>"
