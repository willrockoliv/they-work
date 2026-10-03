"""fase 2: conselho, requisicoes de subagentes e banco de talentos

Revision ID: 0002_fase_2_sociedade
Revises: 0001_schema_inicial
Create Date: 2026-10-03

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0002_fase_2_sociedade'
down_revision: str | None = '0001_schema_inicial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

# Tipos já criados pela 0001: reutilizados sem recriar.
AGENT_ROLE = postgresql.ENUM(
    'CEO', 'CTO', 'CMO', 'CFO', 'RA', 'SUBAGENT', name='agent_role', create_type=False
)
TASK_COMPLEXITY = postgresql.ENUM(
    'TRIVIAL', 'SIMPLE', 'MODERATE', 'COMPLEX', 'CRITICAL',
    name='task_complexity', create_type=False,
)

COMMUNICATION_KIND = postgresql.ENUM(
    'DIRECTIVE', 'ANALYSIS', 'DECISION', 'QUESTION', 'ANSWER', 'REPORT', 'ESCALATION',
    name='communication_kind', create_type=False,
)
REQUEST_STATUS = postgresql.ENUM(
    'DRAFT', 'NEEDS_CLARIFICATION', 'CLARIFIED', 'QUEUED', 'FULFILLED', 'REJECTED', 'CANCELLED',
    name='request_status', create_type=False,
)
NATURE_DECISION = postgresql.ENUM(
    'ALLOWED', 'DOWNGRADED', 'QUEUED', 'BLOCKED', name='nature_decision', create_type=False
)

NEW_AUDIT_EVENTS: tuple[str, ...] = (
    'CHIEF_COMMUNICATION',
    'COUNCIL_DELIBERATION',
    'SUBAGENT_REQUESTED',
    'SUBAGENT_CLARIFICATION',
    'TALENT_PROFILE_CREATED',
    'TALENT_PROFILE_REUSED',
    'TALENT_PROFILE_RATED',
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (COMMUNICATION_KIND, REQUEST_STATUS, NATURE_DECISION):
        enum_type.create(bind, checkfirst=True)

    # `audit_event_type` ganha as categorias da Fase 2.
    for value in NEW_AUDIT_EVENTS:
        op.execute(f"ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        'chief_profiles',
        sa.Column('role', AGENT_ROLE, nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=True),
        sa.Column('headline', sa.String(length=160), nullable=False),
        sa.Column('mission', sa.Text(), nullable=False),
        sa.Column('reasoning_style', sa.Text(), nullable=False),
        sa.Column('objectives', JSONB, nullable=False),
        sa.Column('decision_criteria', JSONB, nullable=False),
        sa.Column('context_memory', JSONB, nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('default_complexity', TASK_COMPLEXITY, nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'],
                                name='fk_chief_profiles_agent_id_agents', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_chief_profiles'),
        sa.UniqueConstraint('role', name='uq_chief_profiles_role'),
    )

    op.create_table(
        'chief_communications',
        sa.Column('thread_id', sa.Uuid(), nullable=False),
        sa.Column('kind', COMMUNICATION_KIND, nullable=False),
        sa.Column('from_role', AGENT_ROLE, nullable=False),
        sa.Column('to_role', AGENT_ROLE, nullable=True),
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=True),
        sa.Column('verdict', sa.String(length=64), nullable=True),
        sa.Column('confidence', sa.Integer(), nullable=False),
        sa.Column('payload', JSONB, nullable=False),
        sa.Column('agent_id', sa.Uuid(), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'],
                                name='fk_chief_communications_agent_id_agents',
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_chief_communications'),
    )
    op.create_index('ix_chief_communications_thread', 'chief_communications',
                    ['thread_id', 'created_at'], unique=False)
    op.create_index('ix_chief_communications_from_kind', 'chief_communications',
                    ['from_role', 'kind'], unique=False)

    op.create_table(
        'subagent_requests',
        sa.Column('requested_by_role', AGENT_ROLE, nullable=False),
        sa.Column('requester_agent_id', sa.Uuid(), nullable=True),
        sa.Column('job_title', sa.String(length=160), nullable=False),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('raw_request', sa.Text(), nullable=False),
        sa.Column('deliverables', JSONB, nullable=False),
        sa.Column('tools', JSONB, nullable=False),
        sa.Column('constraints', JSONB, nullable=False),
        sa.Column('complexity', TASK_COMPLEXITY, nullable=False),
        sa.Column('requested_model', sa.String(length=120), nullable=True),
        sa.Column('status', REQUEST_STATUS, nullable=False),
        sa.Column('clarifications', JSONB, nullable=False),
        sa.Column('nature_decision', NATURE_DECISION, nullable=True),
        sa.Column('nature_narrative', sa.Text(), nullable=True),
        sa.Column('granted_model', sa.String(length=120), nullable=True),
        sa.Column('queue_position', sa.Integer(), nullable=True),
        sa.Column('talent_profile_id', sa.Uuid(), nullable=True),
        sa.Column('reused_profile', sa.Boolean(), nullable=False),
        sa.Column('created_agent_id', sa.Uuid(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_agent_id'], ['agents.id'],
                                name='fk_subagent_requests_created_agent_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['requester_agent_id'], ['agents.id'],
                                name='fk_subagent_requests_requester_agent_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['talent_profile_id'], ['talent_bank.id'],
                                name='fk_subagent_requests_talent_profile_id_talent_bank',
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_subagent_requests'),
    )
    op.create_index('ix_subagent_requests_status_created', 'subagent_requests',
                    ['status', 'created_at'], unique=False)
    op.create_index('ix_subagent_requests_requested_by', 'subagent_requests',
                    ['requested_by_role'], unique=False)

    # --- Banco de Talentos: versionamento, palavras-chave e avaliação --------
    op.add_column('talent_bank',
                  sa.Column('version', sa.Integer(), nullable=False, server_default='1'))
    op.add_column('talent_bank',
                  sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column('talent_bank', sa.Column('supersedes_id', sa.Uuid(), nullable=True))
    op.add_column('talent_bank',
                  sa.Column('keywords', JSONB, nullable=False, server_default='{}'))
    op.add_column('talent_bank',
                  sa.Column('rating_sum', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('talent_bank',
                  sa.Column('rating_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('talent_bank',
                  sa.Column('task_history', JSONB, nullable=False, server_default='{}'))
    op.create_foreign_key('fk_talent_bank_supersedes_id_talent_bank', 'talent_bank',
                          'talent_bank', ['supersedes_id'], ['id'], ondelete='SET NULL')
    op.drop_constraint('uq_talent_bank_slug', 'talent_bank', type_='unique')
    op.create_unique_constraint('uq_talent_bank_slug_version', 'talent_bank', ['slug', 'version'])
    op.create_index('ix_talent_bank_slug_active', 'talent_bank', ['slug', 'is_active'],
                    unique=False)


def downgrade() -> None:
    op.drop_index('ix_talent_bank_slug_active', table_name='talent_bank')
    op.drop_constraint('uq_talent_bank_slug_version', 'talent_bank', type_='unique')
    op.create_unique_constraint('uq_talent_bank_slug', 'talent_bank', ['slug'])
    op.drop_constraint('fk_talent_bank_supersedes_id_talent_bank', 'talent_bank',
                       type_='foreignkey')
    for column in ('task_history', 'rating_count', 'rating_sum', 'keywords',
                   'supersedes_id', 'is_active', 'version'):
        op.drop_column('talent_bank', column)

    op.drop_index('ix_subagent_requests_requested_by', table_name='subagent_requests')
    op.drop_index('ix_subagent_requests_status_created', table_name='subagent_requests')
    op.drop_table('subagent_requests')

    op.drop_index('ix_chief_communications_from_kind', table_name='chief_communications')
    op.drop_index('ix_chief_communications_thread', table_name='chief_communications')
    op.drop_table('chief_communications')

    op.drop_table('chief_profiles')

    bind = op.get_bind()
    for enum_type in (NATURE_DECISION, REQUEST_STATUS, COMMUNICATION_KIND):
        enum_type.drop(bind, checkfirst=True)
    # Valores adicionados a `audit_event_type` permanecem: PostgreSQL não remove rótulos.
