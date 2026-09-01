"""add user invite_token

Revision ID: d4f8a2b6c9e1
Revises: c7b3e4f8a1d2
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f8a2b6c9e1'
down_revision: Union[str, None] = 'c7b3e4f8a1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('invite_token', sa.String(length=64), nullable=True))
    op.add_column('user', sa.Column('invite_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f('ix_user_invite_token'), 'user', ['invite_token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_invite_token'), table_name='user')
    op.drop_column('user', 'invite_token_expires_at')
    op.drop_column('user', 'invite_token')
