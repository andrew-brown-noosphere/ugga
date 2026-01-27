"""Create social features tables and add seeding fields.

Revision ID: 005_social_seeding
Revises: 004_interests
Create Date: 2026-01-27

Creates:
- study_groups table
- study_group_members table
- cohorts table
- cohort_members table
- user_follows table
- profile_likes table

With seeding support:
- study_groups.is_official, nullable organizer_id
- cohorts.org_type, is_official, nullable created_by_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '005_social_seeding'
down_revision: Union[str, None] = '004_interests'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create study_groups table
    op.create_table(
        'study_groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('course_code', sa.String(20), nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('meeting_day', sa.String(20), nullable=True),
        sa.Column('meeting_time', sa.String(50), nullable=True),
        sa.Column('meeting_location', sa.String(200), nullable=True),
        sa.Column('organizer_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('max_members', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create study_group_members table
    op.create_table(
        'study_group_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('study_group_id', sa.Integer(), sa.ForeignKey('study_groups.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_sg_member_unique', 'study_group_members', ['study_group_id', 'user_id'], unique=True)

    # Create cohorts table
    op.create_table(
        'cohorts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('org_type', sa.String(30), nullable=True, index=True),
        sa.Column('is_official', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_by_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('is_public', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('max_members', sa.Integer(), nullable=False, server_default='200'),
        sa.Column('invite_code', sa.String(8), nullable=False, unique=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    # Create cohort_members table
    op.create_table(
        'cohort_members',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('cohort_id', sa.Integer(), sa.ForeignKey('cohorts.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('role', sa.String(20), nullable=False, server_default='member'),
        sa.Column('joined_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_cohort_member_unique', 'cohort_members', ['cohort_id', 'user_id'], unique=True)

    # Create user_follows table
    op.create_table(
        'user_follows',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('follower_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('following_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_follow_unique', 'user_follows', ['follower_id', 'following_id'], unique=True)

    # Create profile_likes table
    op.create_table(
        'profile_likes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('target_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('target_instructor_id', sa.Integer(), sa.ForeignKey('instructors.id'), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_like_user_unique', 'profile_likes', ['user_id', 'target_user_id'], unique=True)
    op.create_index('ix_like_instructor_unique', 'profile_likes', ['user_id', 'target_instructor_id'], unique=True)


def downgrade() -> None:
    op.drop_table('profile_likes')
    op.drop_table('user_follows')
    op.drop_table('cohort_members')
    op.drop_table('cohorts')
    op.drop_table('study_group_members')
    op.drop_table('study_groups')
