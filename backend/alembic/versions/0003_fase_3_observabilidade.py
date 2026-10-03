"""fase 3: observabilidade cognitiva (sessoes e passos ReAct)

Revision ID: 0003_fase_3_observabilidade
Revises: 0002_fase_2_sociedade
Create Date: 2026-10-03

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0003_fase_3_observabilidade'
down_revision: str | None = '0002_fase_2_sociedade'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

# Tipo já criado pela 0001: reutilizado sem recriar.
TASK_COMPLEXITY = postgresql.ENUM(
    'TRIVIAL', 'SIMPLE', 'MODERATE', 'COMPLEX', 'CRITICAL',
    name='task_complexity', create_type=False,
)

REASONING_STATUS = postgresql.ENUM(
    'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED',
    name='reasoning_status', create_type=False,
)
REASONING_STEP_TYPE = postgresql.ENUM(
    'THOUGHT', 'ACTION', 'OBSERVATION', 'CONCLUSION',
    name='reasoning_step_type', create_type=False,
)

NEW_AUDIT_EVENTS: tuple[str, ...] = (
    'REASONING_STARTED',
    'REASONING_COMPLETED',
    'REASONING_FAILED',
    'REASONING_PURGED',
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (REASONING_STATUS, REASONING_STEP_TYPE):
        enum_type.create(bind, checkfirst=True)

    # `audit_event_type` ganha as categorias da Fase 3.
    for value in NEW_AUDIT_EVENTS:
        op.execute(f"ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        'reasoning_sessions',
        sa.Column('agent_id', sa.Uuid(), nullable=True),
        sa.Column('thread_id', sa.Uuid(), nullable=True),
        sa.Column('task', sa.Text(), nullable=False),
        sa.Column('status', REASONING_STATUS, nullable=False),
        sa.Column('complexity', TASK_COMPLEXITY, nullable=False),
        sa.Column('model_name', sa.String(length=120), nullable=True),
        sa.Column('step_count', sa.Integer(), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('estimated_ram_mb', sa.Integer(), nullable=False),
        sa.Column('conclusion', sa.Text(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'],
                                name='fk_reasoning_sessions_agent_id_agents',
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_reasoning_sessions'),
    )
    op.create_index('ix_reasoning_sessions_agent_started', 'reasoning_sessions',
                    ['agent_id', 'started_at'], unique=False)
    op.create_index('ix_reasoning_sessions_status', 'reasoning_sessions',
                    ['status'], unique=False)

    op.create_table(
        'reasoning_steps',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Uuid(), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False),
        sa.Column('step_type', REASONING_STEP_TYPE, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('model_name', sa.String(length=120), nullable=True),
        sa.Column('tokens', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['reasoning_sessions.id'],
                                name='fk_reasoning_steps_session_id_reasoning_sessions',
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name='pk_reasoning_steps'),
    )
    op.create_index('ix_reasoning_steps_session_sequence', 'reasoning_steps',
                    ['session_id', 'sequence'], unique=False)
    op.create_index('ix_reasoning_steps_type', 'reasoning_steps', ['step_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_reasoning_steps_type', table_name='reasoning_steps')
    op.drop_index('ix_reasoning_steps_session_sequence', table_name='reasoning_steps')
    op.drop_table('reasoning_steps')

    op.drop_index('ix_reasoning_sessions_status', table_name='reasoning_sessions')
    op.drop_index('ix_reasoning_sessions_agent_started', table_name='reasoning_sessions')
    op.drop_table('reasoning_sessions')

    bind = op.get_bind()
    for enum_type in (REASONING_STEP_TYPE, REASONING_STATUS):
        enum_type.drop(bind, checkfirst=True)

    # Valores de enum do PostgreSQL não podem ser removidos: `audit_event_type`
    # mantém as categorias REASONING_* mesmo após o downgrade.
