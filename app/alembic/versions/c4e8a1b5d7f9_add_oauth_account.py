"""add oauth_account

Revision ID: c4e8a1b5d7f9
Revises: b3d7f9a2c4e6
Create Date: 2026-10-31 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e8a1b5d7f9'
down_revision: Union[str, None] = 'b3d7f9a2c4e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'oauth_account',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=20), nullable=False),
        sa.Column('account_id', sa.String(length=255), nullable=False),
        sa.Column('account_email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'account_id', name='uq_oauth_account_identity'),
        sa.UniqueConstraint('user_id', 'provider', name='uq_oauth_account_user_provider'),
    )
    op.create_index(op.f('ix_oauth_account_user_id'), 'oauth_account', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_oauth_account_user_id'), table_name='oauth_account')
    op.drop_table('oauth_account')
