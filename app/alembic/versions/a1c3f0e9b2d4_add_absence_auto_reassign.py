"""add absence auto_reassign

Revision ID: a1c3f0e9b2d4
Revises: 43f79b577311
Create Date: 2026-09-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c3f0e9b2d4'
down_revision: Union[str, None] = '43f79b577311'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'absence',
        sa.Column('auto_reassign', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column('absence', 'auto_reassign', server_default=None)


def downgrade() -> None:
    op.drop_column('absence', 'auto_reassign')
