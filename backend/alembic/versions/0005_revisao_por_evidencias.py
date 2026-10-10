"""revisao do chief por evidencias: origem do veredito e evidencias da revisao

Revision ID: 0005_revisao_por_evidencias
Revises: 0004_fase_5_rede_corporativa
Create Date: 2026-10-10

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0005_revisao_por_evidencias'
down_revision: str | None = '0004_fase_5_rede_corporativa'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def upgrade() -> None:
    op.add_column('agent_tasks', sa.Column('decision_source', sa.String(32), nullable=True))
    op.add_column(
        'agent_tasks',
        sa.Column('review_evidence', JSONB, nullable=False, server_default=sa.text("'{}'")),
    )
    op.create_index(
        'ix_agent_tasks_decision_source', 'agent_tasks', ['decision_source'], unique=False
    )


def downgrade() -> None:
    op.drop_index('ix_agent_tasks_decision_source', table_name='agent_tasks')
    op.drop_column('agent_tasks', 'review_evidence')
    op.drop_column('agent_tasks', 'decision_source')
