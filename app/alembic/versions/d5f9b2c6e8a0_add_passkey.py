"""add passkey

Revision ID: d5f9b2c6e8a0
Revises: c4e8a1b5d7f9
Create Date: 2026-10-31 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5f9b2c6e8a0'
down_revision: Union[str, None] = 'c4e8a1b5d7f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'passkey',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('credential_id', sa.String(length=512), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_passkey_user_id'), 'passkey', ['user_id'], unique=False)
    op.create_index(op.f('ix_passkey_credential_id'), 'passkey', ['credential_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_passkey_credential_id'), table_name='passkey')
    op.drop_index(op.f('ix_passkey_user_id'), table_name='passkey')
    op.drop_table('passkey')
