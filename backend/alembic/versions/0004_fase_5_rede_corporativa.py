"""fase 5: rede corporativa (pedidos, tarefas delegadas e grafo de comunicacoes)

Revision ID: 0004_fase_5_rede_corporativa
Revises: 0003_fase_3_observabilidade
Create Date: 2026-10-05

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0004_fase_5_rede_corporativa'
down_revision: str | None = '0003_fase_3_observabilidade'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

INITIAL_REQUEST_STATUS = postgresql.ENUM(
    'PROPOSED', 'DELIBERATING', 'IN_EXECUTION', 'AWAITING_FEEDBACK', 'COMPLETED', 'FAILED',
    name='initial_request_status', create_type=False,
)
TASK_STATUS = postgresql.ENUM(
    'PENDING', 'ACKNOWLEDGED', 'IN_PROGRESS', 'AWAITING_REVIEW', 'COMPLETED', 'REJECTED',
    'CANCELLED',
    name='task_status', create_type=False,
)
CHIEF_DECISION = postgresql.ENUM(
    'APPROVE', 'REJECT', 'MODIFY', 'CONSULT_PEERS', 'ESCALATE',
    name='chief_decision', create_type=False,
)
COMMUNICATION_TYPE = postgresql.ENUM(
    'REQUEST', 'OPINION', 'COORDINATION', 'AGENT_REQUEST', 'AGENT_CREATED', 'DELEGATION',
    'REPORT', 'CONSULTATION', 'ESCALATION', 'DECISION',
    name='communication_type', create_type=False,
)
COMMUNICATION_STATUS = postgresql.ENUM(
    'PENDING', 'ACKNOWLEDGED', 'PROCESSED',
    name='communication_status', create_type=False,
)

NEW_AUDIT_EVENTS: tuple[str, ...] = (
    'REQUEST_SUBMITTED',
    'REQUEST_RESOLVED',
    'AGENT_REQUESTED',
    'TASK_DELEGATED',
    'TASK_REPORTED',
    'TASK_REVIEWED',
    'CHIEF_CONSULTATION',
    'CEO_TIEBREAK',
)


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in (
        INITIAL_REQUEST_STATUS,
        TASK_STATUS,
        CHIEF_DECISION,
        COMMUNICATION_TYPE,
        COMMUNICATION_STATUS,
    ):
        enum_type.create(bind, checkfirst=True)

    for value in NEW_AUDIT_EVENTS:
        op.execute(f"ALTER TYPE audit_event_type ADD VALUE IF NOT EXISTS '{value}'")

    op.create_table(
        'initial_requests',
        sa.Column('topic', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('submitted_by', sa.String(length=120), nullable=False),
        sa.Column('status', INITIAL_REQUEST_STATUS, nullable=False),
        sa.Column('thread_id', sa.Uuid(), nullable=True),
        sa.Column('outcome', sa.String(length=64), nullable=True),
        sa.Column('narrative', sa.Text(), nullable=True),
        sa.Column('current_state', JSONB, nullable=False),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id', name='pk_initial_requests'),
    )
    op.create_index('ix_initial_requests_status_created', 'initial_requests',
                    ['status', 'created_at'], unique=False)

    op.create_table(
        'agent_tasks',
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('parent_task_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_by_chief_id', sa.Uuid(), nullable=True),
        sa.Column('assigned_to_agent_id', sa.Uuid(), nullable=True),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('task_description', sa.Text(), nullable=False),
        sa.Column('context', JSONB, nullable=False),
        sa.Column('status', TASK_STATUS, nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('report_summary', sa.Text(), nullable=True),
        sa.Column('report_reasoning_session_id', sa.Uuid(), nullable=True),
        sa.Column('review_reasoning_session_id', sa.Uuid(), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=False),
        sa.Column('decision', CHIEF_DECISION, nullable=True),
        sa.Column('decision_rationale', sa.Text(), nullable=True),
        sa.Column('delegated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reported_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['initial_requests.id'],
                                name='fk_agent_tasks_request_id_initial_requests',
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_task_id'], ['agent_tasks.id'],
                                name='fk_agent_tasks_parent_task_id_agent_tasks',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_by_chief_id'], ['agents.id'],
                                name='fk_agent_tasks_assigned_by_chief_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['assigned_to_agent_id'], ['agents.id'],
                                name='fk_agent_tasks_assigned_to_agent_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['report_reasoning_session_id'], ['reasoning_sessions.id'],
                                name='fk_agent_tasks_report_reasoning_session_id_reasoning_sessions',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['review_reasoning_session_id'], ['reasoning_sessions.id'],
                                name='fk_agent_tasks_review_reasoning_session_id_reasoning_sessions',
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_agent_tasks'),
    )
    op.create_index('ix_agent_tasks_request_status', 'agent_tasks',
                    ['request_id', 'status'], unique=False)
    op.create_index('ix_agent_tasks_assignee_status', 'agent_tasks',
                    ['assigned_to_agent_id', 'status'], unique=False)
    op.create_index('ix_agent_tasks_chief_status', 'agent_tasks',
                    ['assigned_by_chief_id', 'status'], unique=False)

    op.create_table(
        'communication_graph',
        sa.Column('request_id', sa.Uuid(), nullable=False),
        sa.Column('task_id', sa.Uuid(), nullable=True),
        sa.Column('sender_agent_id', sa.Uuid(), nullable=True),
        sa.Column('recipient_agent_id', sa.Uuid(), nullable=True),
        sa.Column('communication_type', COMMUNICATION_TYPE, nullable=False),
        sa.Column('status', COMMUNICATION_STATUS, nullable=False),
        sa.Column('summary', sa.String(length=255), nullable=False),
        sa.Column('content', JSONB, nullable=False),
        sa.Column('reasoning_session_id', sa.Uuid(), nullable=True),
        sa.Column('responded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['request_id'], ['initial_requests.id'],
                                name='fk_communication_graph_request_id_initial_requests',
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['agent_tasks.id'],
                                name='fk_communication_graph_task_id_agent_tasks',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sender_agent_id'], ['agents.id'],
                                name='fk_communication_graph_sender_agent_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recipient_agent_id'], ['agents.id'],
                                name='fk_communication_graph_recipient_agent_id_agents',
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['reasoning_session_id'], ['reasoning_sessions.id'],
                                name='fk_communication_graph_reasoning_session_id_reasoning_sessions',
                                ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_communication_graph'),
    )
    op.create_index('ix_communication_graph_request_created', 'communication_graph',
                    ['request_id', 'created_at'], unique=False)
    op.create_index('ix_communication_graph_type', 'communication_graph',
                    ['communication_type'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_communication_graph_type', table_name='communication_graph')
    op.drop_index('ix_communication_graph_request_created', table_name='communication_graph')
    op.drop_table('communication_graph')

    op.drop_index('ix_agent_tasks_chief_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_assignee_status', table_name='agent_tasks')
    op.drop_index('ix_agent_tasks_request_status', table_name='agent_tasks')
    op.drop_table('agent_tasks')

    op.drop_index('ix_initial_requests_status_created', table_name='initial_requests')
    op.drop_table('initial_requests')

    bind = op.get_bind()
    for enum_type in (
        COMMUNICATION_STATUS,
        COMMUNICATION_TYPE,
        CHIEF_DECISION,
        TASK_STATUS,
        INITIAL_REQUEST_STATUS,
    ):
        enum_type.drop(bind, checkfirst=True)

    # Valores de enum do PostgreSQL não podem ser removidos: `audit_event_type`
    # mantém as categorias da Fase 5 mesmo após o downgrade.
