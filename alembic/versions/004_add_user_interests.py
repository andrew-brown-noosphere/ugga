"""Add interests field to users table.

Revision ID: 004_interests
Revises: 003_planned
Create Date: 2026-01-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_interests'
down_revision: Union[str, None] = '003_planned'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add interests column to users table (JSON array stored as text)
    op.add_column('users', sa.Column('interests', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'interests')
