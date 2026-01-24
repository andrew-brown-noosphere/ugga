"""Add profile sharing and UGA verification fields

Revision ID: 002_profile
Revises: 001_progress
Create Date: 2024-01-24

Adds:
- UGA email verification fields
- Username for public profiles
- Visibility settings for profile sharing
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_profile'
down_revision = '001_progress'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add UGA email verification fields
    op.add_column('users', sa.Column('uga_email', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('uga_email_verified', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('uga_email_verified_at', sa.DateTime(), nullable=True))
    op.add_column('users', sa.Column('verification_code', sa.String(6), nullable=True))
    op.add_column('users', sa.Column('verification_code_expires', sa.DateTime(), nullable=True))

    # Add username field (unlocked after verification)
    op.add_column('users', sa.Column('username', sa.String(30), nullable=True))

    # Add visibility settings (JSON)
    op.add_column('users', sa.Column('visibility_settings', sa.Text(), nullable=True))

    # Create unique indexes
    op.create_index('ix_users_uga_email', 'users', ['uga_email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_users_username', table_name='users')
    op.drop_index('ix_users_uga_email', table_name='users')

    # Drop columns
    op.drop_column('users', 'visibility_settings')
    op.drop_column('users', 'username')
    op.drop_column('users', 'verification_code_expires')
    op.drop_column('users', 'verification_code')
    op.drop_column('users', 'uga_email_verified_at')
    op.drop_column('users', 'uga_email_verified')
    op.drop_column('users', 'uga_email')
