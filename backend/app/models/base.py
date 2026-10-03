"""Base declarativa e tipos portáveis (PostgreSQL em produção, SQLite nos testes)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, MetaData, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# JSONB no PostgreSQL, JSON genérico nos demais dialetos (testes com SQLite).
JSONType = JSON().with_variant(JSONB(), "postgresql")

UUIDType = Uuid(as_uuid=True)

TimestampType = DateTime(timezone=True)


def utcnow() -> datetime:
    """Timestamp timezone-aware em UTC."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Base declarativa com convenção de nomes estável para o Alembic."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONType}


class UUIDPrimaryKeyMixin:
    """Chave primária UUID gerada na aplicação (sem depender de extensão do PG)."""

    id: Mapped[uuid.UUID] = mapped_column(UUIDType, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    """Colunas de auditoria temporal padrão."""

    created_at: Mapped[datetime] = mapped_column(
        TimestampType, nullable=False, default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampType,
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )
