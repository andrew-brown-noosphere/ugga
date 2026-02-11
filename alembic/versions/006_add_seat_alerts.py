"""Add seat alerts and seat history tables.

Revision ID: 006_seat_alerts
Revises: 005_social_seeding
Create Date: 2026-02-11

Creates:
- seat_alerts table: User alerts for seat availability changes
- seat_history table: Historical seat data for analytics
- instructor_follows table: User follows instructor
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '006_seat_alerts'
down_revision: Union[str, None] = '005_social_seeding'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create seat_alerts table
    op.create_table(
        'seat_alerts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),

        # Section being watched
        sa.Column('crn', sa.String(20), nullable=False, index=True),
        sa.Column('course_code', sa.String(20), nullable=False),
        sa.Column('section_code', sa.String(20), nullable=True),
        sa.Column('term', sa.String(50), nullable=False),

        # Alert configuration
        sa.Column('alert_type', sa.String(20), nullable=False, server_default='seats_available'),
        sa.Column('threshold', sa.Integer(), nullable=False, server_default='1'),

        # Tracking
        sa.Column('last_known_seats', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_checked_at', sa.DateTime(), nullable=True),

        # Status
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true', index=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('notification_sent', sa.Boolean(), nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Index for active alert queries
    op.create_index(
        'ix_seat_alert_active',
        'seat_alerts',
        ['user_id', 'crn', 'is_active']
    )

    # Create seat_history table for analytics
    op.create_table(
        'seat_history',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('section_id', sa.Integer(), sa.ForeignKey('sections.id'), nullable=False, index=True),
        sa.Column('crn', sa.String(20), nullable=False, index=True),

        # Snapshot data
        sa.Column('seats_available', sa.Integer(), nullable=False),
        sa.Column('class_size', sa.Integer(), nullable=False),
        sa.Column('waitlist_count', sa.Integer(), nullable=False, server_default='0'),

        # Computed metrics
        sa.Column('fill_rate', sa.Float(), nullable=True),

        # Timestamp
        sa.Column('recorded_at', sa.DateTime(), nullable=False, server_default=sa.func.now(), index=True),
    )

    # Index for time-series queries
    op.create_index(
        'ix_seat_history_crn_time',
        'seat_history',
        ['crn', 'recorded_at']
    )

    # Create instructor_follows table
    op.create_table(
        'instructor_follows',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('instructor_id', sa.Integer(), sa.ForeignKey('instructors.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        'ix_instructor_follow_unique',
        'instructor_follows',
        ['user_id', 'instructor_id'],
        unique=True
    )


def downgrade() -> None:
    op.drop_table('instructor_follows')
    op.drop_table('seat_history')
    op.drop_table('seat_alerts')
