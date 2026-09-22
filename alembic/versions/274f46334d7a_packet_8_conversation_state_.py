"""packet 8: conversation state, relationship dimensions, memory conversation links

Revision ID: 274f46334d7a
Revises: f276ffd0429f
Create Date: 2026-08-30 07:56:28.062053

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '274f46334d7a'
down_revision: str | None = 'f276ffd0429f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('current_subject', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('initiating_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ending_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('started_sim_day', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('started_sim_period', sa.String(length=32), nullable=True))
        # server_default on every NOT NULL column below so this also applies
        # to a database that already holds conversations rows; new rows take
        # the ORM default.
        batch_op.add_column(sa.Column('related_research_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_wall_post_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_rabbit_hole_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_memory_ids', sa.JSON(), nullable=False, server_default='[]'))

    with op.batch_alter_table('memories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('related_conversation_ids', sa.JSON(), nullable=False, server_default='[]'))

    with op.batch_alter_table('relationships', schema=None) as batch_op:
        # 0.0, not tied to trust_score's friendly 60 baseline: familiarity is
        # purely "how much history exists", which is genuinely zero before
        # any interaction, even between two agents who'd get along fine.
        batch_op.add_column(sa.Column('familiarity', sa.Float(), nullable=False, server_default='0.0'))
        # 50.0 — neutral, not friendly-biased like trust_score: whether two
        # agents specifically enjoy engaging each other's ideas is a genuine
        # unknown at zero interactions, unlike baseline goodwill.
        batch_op.add_column(sa.Column('intellectual_affinity', sa.Float(), nullable=False, server_default='50.0'))
        batch_op.add_column(sa.Column('productive_disagreement_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('relationships', schema=None) as batch_op:
        batch_op.drop_column('productive_disagreement_count')
        batch_op.drop_column('intellectual_affinity')
        batch_op.drop_column('familiarity')

    with op.batch_alter_table('memories', schema=None) as batch_op:
        batch_op.drop_column('related_conversation_ids')

    with op.batch_alter_table('conversations', schema=None) as batch_op:
        batch_op.drop_column('related_memory_ids')
        batch_op.drop_column('related_rabbit_hole_ids')
        batch_op.drop_column('related_wall_post_ids')
        batch_op.drop_column('related_research_ids')
        batch_op.drop_column('started_sim_period')
        batch_op.drop_column('started_sim_day')
        batch_op.drop_column('ending_reason')
        batch_op.drop_column('initiating_reason')
        batch_op.drop_column('current_subject')
        batch_op.drop_column('location')
