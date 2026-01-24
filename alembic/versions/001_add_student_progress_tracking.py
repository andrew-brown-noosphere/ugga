"""Add student progress tracking tables

Revision ID: 001_progress
Revises:
Create Date: 2024-01-24

Tables added:
- user_completed_courses: Student course history with grades
- user_program_enrollments: Student enrollment in degree programs
- user_transcript_summaries: Cached GPA and hours aggregates
- requirement_rules: Flexible rule definitions for requirements
- user_requirement_satisfactions: Degree audit cache
- course_requirement_applications: Course to requirement mapping
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '001_progress'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # user_completed_courses - Course history with grades
    op.create_table(
        'user_completed_courses',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('course_code', sa.String(20), nullable=False, index=True),
        sa.Column('bulletin_course_id', sa.Integer(), sa.ForeignKey('bulletin_courses.id'), nullable=True),
        sa.Column('grade', sa.String(5), nullable=True),  # Optional for privacy
        sa.Column('credit_hours', sa.Integer(), default=3),
        sa.Column('quality_points', sa.Float(), nullable=True),
        sa.Column('semester', sa.String(20), nullable=True),
        sa.Column('year', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(30), default='manual'),
        sa.Column('source_confidence', sa.Float(), nullable=True),
        sa.Column('source_metadata', sa.Text(), nullable=True),
        sa.Column('verified', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_user_completed_user_course', 'user_completed_courses', ['user_id', 'course_code'])
    op.create_index('ix_user_completed_semester', 'user_completed_courses', ['user_id', 'semester'])

    # user_program_enrollments - Links users to degree programs
    op.create_table(
        'user_program_enrollments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('program_id', sa.Integer(), sa.ForeignKey('programs.id'), nullable=False, index=True),
        sa.Column('enrollment_type', sa.String(20), default='major'),
        sa.Column('is_primary', sa.Boolean(), default=True),
        sa.Column('enrollment_date', sa.DateTime(), nullable=True),
        sa.Column('expected_graduation', sa.String(20), nullable=True),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('catalog_year', sa.String(10), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_user_program_enrollment', 'user_program_enrollments', ['user_id', 'program_id'], unique=True)

    # user_transcript_summaries - Cached aggregate statistics
    op.create_table(
        'user_transcript_summaries',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True, index=True),
        sa.Column('total_hours_attempted', sa.Integer(), default=0),
        sa.Column('total_hours_earned', sa.Integer(), default=0),
        sa.Column('transfer_hours', sa.Integer(), default=0),
        sa.Column('cumulative_gpa', sa.Float(), nullable=True),
        sa.Column('major_gpa', sa.Float(), nullable=True),
        sa.Column('total_quality_points', sa.Float(), default=0.0),
        sa.Column('hours_1000_level', sa.Integer(), default=0),
        sa.Column('hours_2000_level', sa.Integer(), default=0),
        sa.Column('hours_3000_level', sa.Integer(), default=0),
        sa.Column('hours_4000_level', sa.Integer(), default=0),
        sa.Column('hours_5000_plus', sa.Integer(), default=0),
        sa.Column('upper_division_hours', sa.Integer(), default=0),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # requirement_rules - Flexible rule definitions
    op.create_table(
        'requirement_rules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('requirement_id', sa.Integer(), sa.ForeignKey('program_requirements.id'), nullable=False, index=True),
        sa.Column('rule_type', sa.String(30), nullable=False),
        sa.Column('rule_config', sa.Text(), nullable=False),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # user_requirement_satisfactions - Audit cache
    op.create_table(
        'user_requirement_satisfactions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('enrollment_id', sa.Integer(), sa.ForeignKey('user_program_enrollments.id'), nullable=False, index=True),
        sa.Column('requirement_id', sa.Integer(), sa.ForeignKey('program_requirements.id'), nullable=False, index=True),
        sa.Column('status', sa.String(20), default='incomplete'),
        sa.Column('hours_required', sa.Integer(), nullable=True),
        sa.Column('hours_satisfied', sa.Integer(), default=0),
        sa.Column('courses_required', sa.Integer(), nullable=True),
        sa.Column('courses_satisfied', sa.Integer(), default=0),
        sa.Column('gpa_required', sa.Float(), nullable=True),
        sa.Column('gpa_achieved', sa.Float(), nullable=True),
        sa.Column('courses_applied_json', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('calculated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_user_req_sat', 'user_requirement_satisfactions', ['user_id', 'enrollment_id', 'requirement_id'], unique=True)

    # course_requirement_applications - Course to requirement mapping
    op.create_table(
        'course_requirement_applications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_completed_course_id', sa.Integer(), sa.ForeignKey('user_completed_courses.id'), nullable=False, index=True),
        sa.Column('satisfaction_id', sa.Integer(), sa.ForeignKey('user_requirement_satisfactions.id'), nullable=False, index=True),
        sa.Column('hours_applied', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), default=True),
        sa.Column('is_manual_override', sa.Boolean(), default=False),
        sa.Column('override_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('ix_course_app_course_sat', 'course_requirement_applications', ['user_completed_course_id', 'satisfaction_id'], unique=True)


def downgrade() -> None:
    op.drop_table('course_requirement_applications')
    op.drop_table('user_requirement_satisfactions')
    op.drop_table('requirement_rules')
    op.drop_table('user_transcript_summaries')
    op.drop_table('user_program_enrollments')
    op.drop_table('user_completed_courses')
