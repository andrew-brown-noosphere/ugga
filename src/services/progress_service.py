"""
Student Progress Service.

Handles CRUD operations for:
- Completed courses
- Program enrollments
- Transcript summary calculations

Auto-recalculates GPA and hour totals when courses change.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import Session

from src.models.database import (
    User, UserCompletedCourse, UserProgramEnrollment, UserTranscriptSummary,
    BulletinCourse, Program,
    get_engine, get_session_factory
)


# Grade to points conversion
GRADE_POINTS = {
    'A': 4.0, 'A-': 3.7,
    'B+': 3.3, 'B': 3.0, 'B-': 2.7,
    'C+': 2.3, 'C': 2.0, 'C-': 1.7,
    'D': 1.0, 'F': 0.0
}

# Grades that count toward GPA
GPA_GRADES = set(GRADE_POINTS.keys())

# Grades that earn credit
PASSING_GRADES = {'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D', 'S'}


class ProgressService:
    """Service for managing student progress and completed courses."""

    def __init__(self, session_factory=None):
        if session_factory is None:
            engine = get_engine()
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    # =========================================================================
    # Completed Courses CRUD
    # =========================================================================

    def add_completed_course(
        self,
        user_id: int,
        course_code: str,
        grade: Optional[str] = None,
        credit_hours: int = 3,
        semester: Optional[str] = None,
        year: Optional[int] = None,
        source: str = "manual",
    ) -> UserCompletedCourse:
        """
        Add a completed course for a user.

        Auto-links to bulletin course if found.
        Recalculates transcript summary after adding.
        Grade is optional for privacy - GPA will only be calculated if grades are provided.
        """
        if grade:
            grade = grade.upper().strip()
        course_code = self._normalize_course_code(course_code)

        with self.session_factory() as session:
            # Check if course already exists for user
            existing = session.execute(
                select(UserCompletedCourse)
                .where(and_(
                    UserCompletedCourse.user_id == user_id,
                    UserCompletedCourse.course_code == course_code,
                ))
            ).scalar_one_or_none()

            if existing:
                raise ValueError(f"Course {course_code} already recorded for this user")

            # Look up bulletin course
            bulletin_course = session.execute(
                select(BulletinCourse)
                .where(BulletinCourse.course_code == course_code)
            ).scalar_one_or_none()

            # Calculate quality points (only if grade provided)
            quality_points = None
            if grade and grade in GRADE_POINTS:
                quality_points = GRADE_POINTS[grade] * credit_hours

            # Create completed course record
            completed = UserCompletedCourse(
                user_id=user_id,
                course_code=course_code,
                bulletin_course_id=bulletin_course.id if bulletin_course else None,
                grade=grade,  # Can be None for privacy
                credit_hours=credit_hours,
                quality_points=quality_points,
                semester=semester,
                year=year,
                source=source,
            )
            session.add(completed)
            session.commit()
            session.refresh(completed)

            # Recalculate transcript summary
            self._recalculate_transcript_summary(session, user_id)
            session.commit()

            return completed

    def add_completed_courses_bulk(
        self,
        user_id: int,
        courses: list[dict],
        source: str = "manual",
    ) -> list[UserCompletedCourse]:
        """
        Add multiple completed courses at once.

        Each course dict should have: course_code, grade, credit_hours (optional),
        semester (optional), year (optional).

        More efficient than adding one at a time - only recalculates once.
        """
        with self.session_factory() as session:
            # Get existing course codes for this user
            existing_codes = set(
                session.execute(
                    select(UserCompletedCourse.course_code)
                    .where(UserCompletedCourse.user_id == user_id)
                ).scalars().all()
            )

            # Bulk lookup bulletin courses
            course_codes = [self._normalize_course_code(c["course_code"]) for c in courses]
            bulletin_map = {}
            bulletin_courses = session.execute(
                select(BulletinCourse)
                .where(BulletinCourse.course_code.in_(course_codes))
            ).scalars().all()
            for bc in bulletin_courses:
                bulletin_map[bc.course_code] = bc.id

            completed_list = []
            for course_data in courses:
                code = self._normalize_course_code(course_data["course_code"])
                grade = course_data.get("grade")
                if grade:
                    grade = grade.upper().strip()
                credit_hours = course_data.get("credit_hours", 3)

                # Skip if already exists
                if code in existing_codes:
                    continue
                existing_codes.add(code)

                # Calculate quality points (only if grade provided)
                quality_points = None
                if grade and grade in GRADE_POINTS:
                    quality_points = GRADE_POINTS[grade] * credit_hours

                completed = UserCompletedCourse(
                    user_id=user_id,
                    course_code=code,
                    bulletin_course_id=bulletin_map.get(code),
                    grade=grade,  # Can be None for privacy
                    credit_hours=credit_hours,
                    quality_points=quality_points,
                    semester=course_data.get("semester"),
                    year=course_data.get("year"),
                    source=source,
                )
                session.add(completed)
                completed_list.append(completed)

            session.commit()

            # Refresh all to get IDs
            for c in completed_list:
                session.refresh(c)

            # Recalculate transcript summary once
            self._recalculate_transcript_summary(session, user_id)
            session.commit()

            return completed_list

    def update_completed_course(
        self,
        course_id: int,
        grade: Optional[str] = None,
        credit_hours: Optional[int] = None,
        semester: Optional[str] = None,
        year: Optional[int] = None,
    ) -> UserCompletedCourse:
        """Update a completed course record."""
        with self.session_factory() as session:
            completed = session.get(UserCompletedCourse, course_id)
            if not completed:
                raise ValueError(f"Completed course {course_id} not found")

            if grade is not None:
                completed.grade = grade.upper().strip()
            if credit_hours is not None:
                completed.credit_hours = credit_hours
            if semester is not None:
                completed.semester = semester
            if year is not None:
                completed.year = year

            # Recalculate quality points
            if completed.grade in GRADE_POINTS:
                completed.quality_points = GRADE_POINTS[completed.grade] * completed.credit_hours
            else:
                completed.quality_points = None

            completed.updated_at = datetime.utcnow()
            session.commit()

            # Recalculate transcript summary
            self._recalculate_transcript_summary(session, completed.user_id)
            session.commit()

            session.refresh(completed)
            return completed

    def delete_completed_course(self, course_id: int) -> bool:
        """Delete a completed course record."""
        with self.session_factory() as session:
            completed = session.get(UserCompletedCourse, course_id)
            if not completed:
                return False

            user_id = completed.user_id
            session.delete(completed)
            session.commit()

            # Recalculate transcript summary
            self._recalculate_transcript_summary(session, user_id)
            session.commit()

            return True

    def get_completed_courses(
        self,
        user_id: int,
        semester: Optional[str] = None,
    ) -> list[UserCompletedCourse]:
        """Get all completed courses for a user, optionally filtered by semester."""
        with self.session_factory() as session:
            query = (
                select(UserCompletedCourse)
                .where(UserCompletedCourse.user_id == user_id)
            )

            if semester:
                query = query.where(UserCompletedCourse.semester == semester)

            query = query.order_by(
                UserCompletedCourse.year.desc().nullslast(),
                UserCompletedCourse.semester.desc().nullslast(),
                UserCompletedCourse.course_code,
            )

            return list(session.execute(query).scalars().all())

    def get_completed_course_codes(self, user_id: int) -> set[str]:
        """Get set of completed course codes for a user (for prerequisite checking)."""
        with self.session_factory() as session:
            codes = session.execute(
                select(UserCompletedCourse.course_code)
                .where(UserCompletedCourse.user_id == user_id)
            ).scalars().all()
            return set(codes)

    # =========================================================================
    # Program Enrollments
    # =========================================================================

    def enroll_in_program(
        self,
        user_id: int,
        program_id: int,
        enrollment_type: str = "major",
        is_primary: bool = True,
        catalog_year: Optional[str] = None,
    ) -> UserProgramEnrollment:
        """Enroll a user in a degree program."""
        with self.session_factory() as session:
            # Check if already enrolled
            existing = session.execute(
                select(UserProgramEnrollment)
                .where(and_(
                    UserProgramEnrollment.user_id == user_id,
                    UserProgramEnrollment.program_id == program_id,
                ))
            ).scalar_one_or_none()

            if existing:
                raise ValueError("User already enrolled in this program")

            # If setting as primary, unset other primary enrollments
            if is_primary:
                session.execute(
                    select(UserProgramEnrollment)
                    .where(and_(
                        UserProgramEnrollment.user_id == user_id,
                        UserProgramEnrollment.is_primary == True,
                    ))
                )
                for enrollment in session.execute(
                    select(UserProgramEnrollment)
                    .where(and_(
                        UserProgramEnrollment.user_id == user_id,
                        UserProgramEnrollment.is_primary == True,
                    ))
                ).scalars().all():
                    enrollment.is_primary = False

            enrollment = UserProgramEnrollment(
                user_id=user_id,
                program_id=program_id,
                enrollment_type=enrollment_type,
                is_primary=is_primary,
                catalog_year=catalog_year,
                enrollment_date=datetime.utcnow(),
            )
            session.add(enrollment)
            session.commit()
            session.refresh(enrollment)

            return enrollment

    def get_program_enrollments(
        self,
        user_id: int,
        active_only: bool = True,
    ) -> list[UserProgramEnrollment]:
        """Get user's program enrollments."""
        with self.session_factory() as session:
            query = (
                select(UserProgramEnrollment)
                .where(UserProgramEnrollment.user_id == user_id)
            )

            if active_only:
                query = query.where(UserProgramEnrollment.status == "active")

            query = query.order_by(
                UserProgramEnrollment.is_primary.desc(),
                UserProgramEnrollment.enrollment_type,
            )

            return list(session.execute(query).scalars().all())

    def get_primary_enrollment(self, user_id: int) -> Optional[UserProgramEnrollment]:
        """Get user's primary program enrollment."""
        with self.session_factory() as session:
            return session.execute(
                select(UserProgramEnrollment)
                .where(and_(
                    UserProgramEnrollment.user_id == user_id,
                    UserProgramEnrollment.is_primary == True,
                    UserProgramEnrollment.status == "active",
                ))
            ).scalar_one_or_none()

    # =========================================================================
    # Transcript Summary
    # =========================================================================

    def get_transcript_summary(self, user_id: int) -> Optional[UserTranscriptSummary]:
        """Get user's transcript summary."""
        with self.session_factory() as session:
            return session.execute(
                select(UserTranscriptSummary)
                .where(UserTranscriptSummary.user_id == user_id)
            ).scalar_one_or_none()

    def _recalculate_transcript_summary(self, session: Session, user_id: int) -> None:
        """
        Recalculate all transcript summary fields from completed courses.

        Called automatically when courses are added/updated/deleted.
        """
        # Get all completed courses
        courses = session.execute(
            select(UserCompletedCourse)
            .where(UserCompletedCourse.user_id == user_id)
        ).scalars().all()

        # Initialize counters
        total_hours_attempted = 0
        total_hours_earned = 0
        total_quality_points = 0.0
        gpa_hours = 0

        hours_by_level = {
            1000: 0, 2000: 0, 3000: 0, 4000: 0, 5000: 0
        }

        for course in courses:
            credit_hours = course.credit_hours or 3
            grade = course.grade.upper() if course.grade else None

            # Attempted hours (everything except W, I, or no grade)
            if grade and grade not in ('W', 'I', 'IP'):
                total_hours_attempted += credit_hours

            # Earned hours (passing grades or no grade - assume passed)
            if not grade or grade in PASSING_GRADES:
                total_hours_earned += credit_hours

            # GPA calculation (only if grade provided and GPA-bearing)
            if grade and grade in GPA_GRADES:
                gpa_hours += credit_hours
                total_quality_points += GRADE_POINTS[grade] * credit_hours

            # Hours by level
            try:
                level = int(course.course_code.split()[-1][0]) * 1000
                if level >= 5000:
                    hours_by_level[5000] += credit_hours
                elif level >= 1000:
                    hours_by_level[level] += credit_hours
            except (ValueError, IndexError):
                pass  # Skip malformed course codes

        # Calculate GPA
        cumulative_gpa = None
        if gpa_hours > 0:
            cumulative_gpa = round(total_quality_points / gpa_hours, 3)

        # Upper division = 3000+
        upper_division_hours = (
            hours_by_level[3000] + hours_by_level[4000] + hours_by_level[5000]
        )

        # Get or create transcript summary
        summary = session.execute(
            select(UserTranscriptSummary)
            .where(UserTranscriptSummary.user_id == user_id)
        ).scalar_one_or_none()

        if summary is None:
            summary = UserTranscriptSummary(user_id=user_id)
            session.add(summary)

        # Update summary
        summary.total_hours_attempted = total_hours_attempted
        summary.total_hours_earned = total_hours_earned
        summary.total_quality_points = total_quality_points
        summary.cumulative_gpa = cumulative_gpa
        summary.hours_1000_level = hours_by_level[1000]
        summary.hours_2000_level = hours_by_level[2000]
        summary.hours_3000_level = hours_by_level[3000]
        summary.hours_4000_level = hours_by_level[4000]
        summary.hours_5000_plus = hours_by_level[5000]
        summary.upper_division_hours = upper_division_hours
        summary.calculated_at = datetime.utcnow()

    # =========================================================================
    # Utilities
    # =========================================================================

    def _normalize_course_code(self, code: str) -> str:
        """
        Normalize course code to standard format: SUBJ 1234

        Handles variations like:
        - "CSCI1301" -> "CSCI 1301"
        - "csci 1301" -> "CSCI 1301"
        - "CSCI  1301" -> "CSCI 1301"
        """
        code = code.upper().strip()

        # Handle no space between subject and number
        import re
        match = re.match(r'^([A-Z]{2,4})\s*(\d{4}[A-Z]?)$', code)
        if match:
            return f"{match.group(1)} {match.group(2)}"

        # Already has space, just normalize whitespace
        parts = code.split()
        if len(parts) == 2:
            return f"{parts[0]} {parts[1]}"

        return code  # Return as-is if can't parse


def create_progress_service() -> ProgressService:
    """Create a ProgressService instance with default configuration."""
    return ProgressService()
