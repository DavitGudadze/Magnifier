"""Add is_google_user column to users table

Revision ID: a1b2c3d4e5f6
Revises: 63aad5679d86
Create Date: 2025-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = '63aad5679d86'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users',
        sa.Column('is_google_user', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade():
    op.drop_column('users', 'is_google_user')
