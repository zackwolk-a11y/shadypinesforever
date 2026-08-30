"""packet 7: memory, interests, and relationship evolution

Revision ID: f276ffd0429f
Revises: ea12ac3f2572
Create Date: 2026-08-30 07:23:13.640782

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = 'f276ffd0429f'
down_revision: str | None = 'ea12ac3f2572'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('agent_interests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_engaged_sim_day', sa.Integer(), nullable=True))
        # server_default on every NOT NULL column below so this also applies
        # to a database that already holds agent_interests rows (the
        # Founding Eight, seeded by scripts/seed_agents.py); new rows take
        # the ORM default.
        batch_op.add_column(sa.Column('dormant', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('supporting_research_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('supporting_event_ids', sa.JSON(), nullable=False, server_default='[]'))
        # No good historical value for a founding interest's creation time,
        # so it backfills to "now" (migration time) — accurate enough for a
        # column that only matters for how *new* interests age from here on.
        batch_op.add_column(
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                      server_default=sa.text('CURRENT_TIMESTAMP'))
        )

    with op.batch_alter_table('memories', schema=None) as batch_op:
        # A rename, not a drop+add: any WRITE_NOTE memory already on disk
        # keeps its recall history. related_ids (a generic, untyped bag) is a
        # genuine removal — Packet 7 replaces it with four typed lists below,
        # which is a real behavior change, not just a rename.
        batch_op.alter_column('last_recalled', new_column_name='last_accessed')
        batch_op.add_column(sa.Column('importance', sa.Float(), nullable=False, server_default='30.0'))
        batch_op.add_column(sa.Column('confidence', sa.Float(), nullable=False, server_default='70.0'))
        batch_op.add_column(sa.Column('created_sim_day', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_accessed_sim_day', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('source_event_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_research_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_agent_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_rabbit_hole_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('related_belief_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('decay_score', sa.Float(), nullable=False, server_default='1.0'))
        batch_op.add_column(sa.Column('reinforcement_count', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_column('related_ids')

    with op.batch_alter_table('relationships', schema=None) as batch_op:
        # 60.0, not a neutral 50 — friendship is the Village's baseline
        # (§10), not something a relationship starts at zero and earns.
        batch_op.add_column(sa.Column('trust_score', sa.Float(), nullable=False, server_default='60.0'))
        batch_op.add_column(sa.Column('interaction_count', sa.Integer(), nullable=False, server_default='0'))


def downgrade() -> None:
    with op.batch_alter_table('relationships', schema=None) as batch_op:
        batch_op.drop_column('interaction_count')
        batch_op.drop_column('trust_score')

    with op.batch_alter_table('memories', schema=None) as batch_op:
        batch_op.add_column(sa.Column('related_ids', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.drop_column('reinforcement_count')
        batch_op.drop_column('decay_score')
        batch_op.drop_column('related_belief_ids')
        batch_op.drop_column('related_rabbit_hole_ids')
        batch_op.drop_column('related_agent_ids')
        batch_op.drop_column('related_research_ids')
        batch_op.drop_column('source_event_ids')
        batch_op.drop_column('last_accessed_sim_day')
        batch_op.drop_column('created_sim_day')
        batch_op.drop_column('confidence')
        batch_op.drop_column('importance')
        batch_op.alter_column('last_accessed', new_column_name='last_recalled')

    with op.batch_alter_table('agent_interests', schema=None) as batch_op:
        batch_op.drop_column('created_at')
        batch_op.drop_column('supporting_event_ids')
        batch_op.drop_column('supporting_research_ids')
        batch_op.drop_column('dormant')
        batch_op.drop_column('last_engaged_sim_day')
