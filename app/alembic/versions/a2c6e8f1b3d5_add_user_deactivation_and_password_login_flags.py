"""add user deactivated_at and password_login_enabled

Revision ID: a2c6e8f1b3d5
Revises: d9e5b2c7f4a8
Create Date: 2026-10-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c6e8f1b3d5'
down_revision: Union[str, None] = 'd9e5b2c7f4a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('deactivated_at', sa.DateTime(timezone=True), nullable=True))
    # server_default so existing rows are valid as-is: current members keep password login on.
    op.add_column(
        'user',
        sa.Column('password_login_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('user', 'password_login_enabled')
    op.drop_column('user', 'deactivated_at')
