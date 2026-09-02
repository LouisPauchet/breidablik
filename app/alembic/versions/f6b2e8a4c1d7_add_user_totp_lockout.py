"""add user totp lockout counters

Revision ID: f6b2e8a4c1d7
Revises: e5a1c9d3f7b2
Create Date: 2026-09-02 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b2e8a4c1d7'
down_revision: Union[str, None] = 'e5a1c9d3f7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'user', sa.Column('totp_failed_attempts', sa.Integer(), nullable=False, server_default='0')
    )
    op.add_column('user', sa.Column('totp_locked_until', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'totp_locked_until')
    op.drop_column('user', 'totp_failed_attempts')
