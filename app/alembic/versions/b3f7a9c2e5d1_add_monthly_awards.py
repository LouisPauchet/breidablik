"""add monthly awards

Revision ID: b3f7a9c2e5d1
Revises: f6b2e8a4c1d7
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b3f7a9c2e5d1'
down_revision: Union[str, None] = 'f6b2e8a4c1d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # award_cycle and award_category_suggestion reference each other (cycle -> drawn
    # suggestion, suggestion -> cycle), so award_cycle is created first without
    # drawn_suggestion_id, then award_category_suggestion, then the FK is added back.
    op.create_table(
        'award_cycle',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('month', sa.Date(), nullable=False),
        sa.Column(
            'phase',
            sa.Enum('suggesting', 'voting', 'decided', name='awardcyclephase'),
            nullable=False,
        ),
        sa.Column('suggestion_window_opened_at', sa.DateTime(), nullable=True),
        sa.Column('voting_window_opened_at', sa.DateTime(), nullable=True),
        sa.Column('finalized_at', sa.DateTime(), nullable=True),
        sa.Column('drawn_suggestion_id', sa.Uuid(), nullable=True),
        sa.Column('duty_master_winner_id', sa.Uuid(), nullable=True),
        sa.Column('duty_master_win_count', sa.Integer(), nullable=True),
        sa.Column('community_award_winner_id', sa.Uuid(), nullable=True),
        sa.Column('community_award_vote_count', sa.Integer(), nullable=True),
        sa.Column('community_award_vetoed', sa.Boolean(), nullable=False),
        sa.Column('community_award_veto_by_id', sa.Uuid(), nullable=True),
        sa.Column('community_award_veto_at', sa.DateTime(), nullable=True),
        sa.Column('community_award_veto_reason', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['duty_master_winner_id'], ['user.id']),
        sa.ForeignKeyConstraint(['community_award_winner_id'], ['user.id']),
        sa.ForeignKeyConstraint(['community_award_veto_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('month'),
    )
    op.create_index(op.f('ix_award_cycle_month'), 'award_cycle', ['month'], unique=True)

    op.create_table(
        'award_category_suggestion',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cycle_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=100), nullable=False),
        sa.Column('emoji', sa.String(length=32), nullable=False),
        sa.Column('suggested_by_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cycle_id'], ['award_cycle.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['suggested_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cycle_id', 'suggested_by_id', name='uq_award_suggestion_member_per_cycle'),
    )
    op.create_index(
        op.f('ix_award_category_suggestion_cycle_id'), 'award_category_suggestion', ['cycle_id'], unique=False
    )

    op.create_foreign_key(
        'fk_award_cycle_drawn_suggestion_id',
        'award_cycle',
        'award_category_suggestion',
        ['drawn_suggestion_id'],
        ['id'],
    )

    op.create_table(
        'award_category_vote',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cycle_id', sa.Uuid(), nullable=False),
        sa.Column('voter_id', sa.Uuid(), nullable=False),
        sa.Column('candidate_id', sa.Uuid(), nullable=False),
        sa.Column('voted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cycle_id'], ['award_cycle.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['voter_id'], ['user.id']),
        sa.ForeignKeyConstraint(['candidate_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cycle_id', 'voter_id', name='uq_award_vote_one_per_voter_per_cycle'),
    )
    op.create_index(op.f('ix_award_category_vote_cycle_id'), 'award_category_vote', ['cycle_id'], unique=False)
    op.create_index(
        op.f('ix_award_category_vote_candidate_id'), 'award_category_vote', ['candidate_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_award_category_vote_candidate_id'), table_name='award_category_vote')
    op.drop_index(op.f('ix_award_category_vote_cycle_id'), table_name='award_category_vote')
    op.drop_table('award_category_vote')

    op.drop_constraint('fk_award_cycle_drawn_suggestion_id', 'award_cycle', type_='foreignkey')

    op.drop_index(op.f('ix_award_category_suggestion_cycle_id'), table_name='award_category_suggestion')
    op.drop_table('award_category_suggestion')

    op.drop_index(op.f('ix_award_cycle_month'), table_name='award_cycle')
    op.drop_table('award_cycle')

    sa.Enum(name='awardcyclephase').drop(op.get_bind(), checkfirst=True)
