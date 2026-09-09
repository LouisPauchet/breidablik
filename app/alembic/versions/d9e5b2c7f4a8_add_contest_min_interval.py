"""add contest min_interval_minutes and show_on_home

Revision ID: d9e5b2c7f4a8
Revises: c8d4f1a6e9b3
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e5b2c7f4a8'
down_revision: Union[str, None] = 'c8d4f1a6e9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'contest_duty',
        sa.Column('min_interval_minutes', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'contest_duty',
        sa.Column('show_on_home', sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column('contest_duty', 'show_on_home')
    op.drop_column('contest_duty', 'min_interval_minutes')
