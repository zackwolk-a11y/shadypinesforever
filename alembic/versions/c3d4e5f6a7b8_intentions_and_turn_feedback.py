"""intentions and turn feedback (the intention -> action bridge)

Revision ID: c3d4e5f6a7b8
Revises: a11c5ab569f8
Create Date: 2026-10-20 12:00:00.000000

Additive only: two new tables, no existing column touched. Safe to apply to a
disposable clone first; apply to the canonical live database only with
Founder authorization, after a backup (app.core.db_safety.create_backup).
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'a11c5ab569f8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('intentions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('planned_action', sa.String(length=64), nullable=False),
    sa.Column('with_agent_id', sa.String(length=64), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'FULFILLED', 'DROPPED', 'EXPIRED', name='intention_status'), nullable=False),
    sa.Column('source_conversation_id', sa.Integer(), nullable=True),
    sa.Column('source_event_id', sa.Integer(), nullable=True),
    sa.Column('created_sim_day', sa.Integer(), nullable=True),
    sa.Column('created_sim_period', sa.String(length=32), nullable=True),
    sa.Column('created_period_index', sa.Integer(), nullable=False),
    sa.Column('closed_event_id', sa.Integer(), nullable=True),
    sa.Column('closed_sim_day', sa.Integer(), nullable=True),
    sa.Column('closed_sim_period', sa.String(length=32), nullable=True),
    sa.Column('fulfilled_by_action', sa.String(length=64), nullable=True),
    sa.Column('fulfilled_explicitly', sa.Boolean(), nullable=True),
    sa.Column('fulfilled_entity', sa.JSON(), nullable=True),
    sa.Column('close_note', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], name=op.f('fk_intentions_agent_id_agents')),
    sa.ForeignKeyConstraint(['with_agent_id'], ['agents.agent_id'], name=op.f('fk_intentions_with_agent_id_agents')),
    sa.ForeignKeyConstraint(['source_conversation_id'], ['conversations.id'], name=op.f('fk_intentions_source_conversation_id_conversations')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_intentions'))
    )
    with op.batch_alter_table('intentions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_intentions_agent_id'), ['agent_id'], unique=False)

    op.create_table('agent_feedback',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('agent_id', sa.String(length=64), nullable=False),
    sa.Column('kind', sa.String(length=48), nullable=False),
    sa.Column('note', sa.Text(), nullable=False),
    sa.Column('source_event_id', sa.Integer(), nullable=True),
    sa.Column('detail', sa.JSON(), nullable=False),
    sa.Column('created_sim_day', sa.Integer(), nullable=True),
    sa.Column('shown_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('addressed', sa.Boolean(), nullable=True),
    sa.Column('judged_event_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id'], name=op.f('fk_agent_feedback_agent_id_agents')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_feedback'))
    )
    with op.batch_alter_table('agent_feedback', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_feedback_agent_id'), ['agent_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('agent_feedback', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agent_feedback_agent_id'))
    op.drop_table('agent_feedback')
    with op.batch_alter_table('intentions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_intentions_agent_id'))
    op.drop_table('intentions')
