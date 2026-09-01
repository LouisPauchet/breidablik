"""add dashboard_config

Revision ID: e5a1c9d3f7b2
Revises: d4f8a2b6c9e1
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a1c9d3f7b2'
down_revision: Union[str, None] = 'd4f8a2b6c9e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'dashboard_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_dashboard_config_token'), 'dashboard_config', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_dashboard_config_token'), table_name='dashboard_config')
    op.drop_table('dashboard_config')
