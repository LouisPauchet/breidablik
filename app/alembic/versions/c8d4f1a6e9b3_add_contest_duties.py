"""add contest duties

Revision ID: c8d4f1a6e9b3
Revises: b3f7a9c2e5d1
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c8d4f1a6e9b3'
down_revision: Union[str, None] = 'b3f7a9c2e5d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'contest_duty',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('icon', sa.String(length=32), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by_id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'contest_log_entry',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('contest_duty_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('logged_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contest_duty_id'], ['contest_duty.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_contest_log_entry_contest_duty_id'), 'contest_log_entry', ['contest_duty_id'], unique=False
    )

    op.create_table(
        'contest_award_result',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('cycle_id', sa.Uuid(), nullable=False),
        sa.Column('contest_duty_id', sa.Uuid(), nullable=False),
        sa.Column('winner_id', sa.Uuid(), nullable=True),
        sa.Column('completion_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['cycle_id'], ['award_cycle.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['contest_duty_id'], ['contest_duty.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('cycle_id', 'contest_duty_id', name='uq_contest_award_result_cycle_duty'),
    )
    op.create_index(
        op.f('ix_contest_award_result_cycle_id'), 'contest_award_result', ['cycle_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_contest_award_result_cycle_id'), table_name='contest_award_result')
    op.drop_table('contest_award_result')

    op.drop_index(op.f('ix_contest_log_entry_contest_duty_id'), table_name='contest_log_entry')
    op.drop_table('contest_log_entry')

    op.drop_table('contest_duty')
