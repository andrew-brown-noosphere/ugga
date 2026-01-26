"""Add planned sections table

Revision ID: 003_planned
Revises: 002_profile
Create Date: 2026-01-26

Adds planned_sections table for users to save sections they want to register for.
"""
from alembic import op
import sqlalchemy as sa


revision = '003_planned'
down_revision = '002_profile'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'planned_sections',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('crn', sa.String(10), nullable=False),
        sa.Column('course_code', sa.String(20), nullable=False),
        sa.Column('course_title', sa.String(200), nullable=True),
        sa.Column('instructor', sa.String(100), nullable=True),
        sa.Column('days', sa.String(20), nullable=True),
        sa.Column('start_time', sa.String(20), nullable=True),
        sa.Column('end_time', sa.String(20), nullable=True),
        sa.Column('building', sa.String(50), nullable=True),
        sa.Column('room', sa.String(20), nullable=True),
        sa.Column('semester', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
    )

    op.create_index('ix_planned_sections_user_id', 'planned_sections', ['user_id'])
    op.create_index('ix_planned_sections_course_code', 'planned_sections', ['course_code'])
    op.create_index('ix_planned_sections_semester', 'planned_sections', ['semester'])
    op.create_index('ix_planned_section_user_semester', 'planned_sections', ['user_id', 'semester'])
    op.create_index('ix_planned_section_unique', 'planned_sections', ['user_id', 'crn', 'semester'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_planned_section_unique', table_name='planned_sections')
    op.drop_index('ix_planned_section_user_semester', table_name='planned_sections')
    op.drop_index('ix_planned_sections_semester', table_name='planned_sections')
    op.drop_index('ix_planned_sections_course_code', table_name='planned_sections')
    op.drop_index('ix_planned_sections_user_id', table_name='planned_sections')
    op.drop_table('planned_sections')
