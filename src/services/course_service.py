"""
Service layer for course data operations.

Handles importing parsed schedules into the database and querying course data.
Uses PostgreSQL with pgvector for vector search capabilities.
"""
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
from sqlalchemy import select, func, and_, or_
from sqlalchemy.orm import Session, selectinload

from src.models.database import (
    Schedule, Course, Section, Instructor,
    get_engine, get_session_factory, init_db
)
from src.models.course import Schedule as ParsedSchedule, Course as ParsedCourse
from src.parsers.uga_pdf_parser import parse_uga_schedule, ParseResult

logger = logging.getLogger(__name__)


class CourseService:
    """Service for managing course data in the database."""

    def __init__(self, session_factory=None):
        """Initialize CourseService with PostgreSQL."""
        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    def import_schedule(
        self,
        parsed: ParsedSchedule,
        source_hash: Optional[str] = None,
        mark_as_current: bool = True
    ) -> Schedule:
        """
        Import a parsed schedule into the database.

        Args:
            parsed: ParsedSchedule object from the parser
            source_hash: Optional hash of the source file for deduplication
            mark_as_current: If True, mark this schedule as current and unmark others

        Returns:
            The created Schedule database object
        """
        with self.session_factory() as session:
            # Check for duplicate import
            if source_hash:
                existing = session.execute(
                    select(Schedule).where(Schedule.source_hash == source_hash)
                ).scalar_one_or_none()
                if existing:
                    return existing

            # Mark previous schedules as not current
            if mark_as_current:
                session.execute(
                    Schedule.__table__.update()
                    .where(Schedule.term == parsed.metadata.term)
                    .values(is_current=False)
                )

            # Create schedule record
            schedule = Schedule(
                term=parsed.metadata.term,
                source_url=parsed.metadata.source_url,
                source_hash=source_hash,
                parse_date=parsed.metadata.parse_date,
                report_date=parsed.metadata.report_date,
                total_courses=parsed.metadata.total_courses,
                total_sections=parsed.metadata.total_sections,
                is_current=mark_as_current,
            )
            session.add(schedule)
            session.flush()  # Get the schedule ID

            # Track instructors
            instructor_cache: dict[str, Instructor] = {}

            # Import courses and sections
            for parsed_course in parsed.courses:
                course = Course(
                    schedule_id=schedule.id,
                    subject=parsed_course.subject,
                    course_number=parsed_course.course_number,
                    title=parsed_course.title,
                    department=parsed_course.department,
                    bulletin_url=parsed_course.bulletin_url,
                    course_code=parsed_course.course_code,
                )
                session.add(course)
                session.flush()

                for parsed_section in parsed_course.sections:
                    # Calculate waitlist from negative seats
                    waitlist = 0
                    seats = parsed_section.seats_available
                    if seats < 0:
                        waitlist = abs(seats)
                        seats = 0

                    section = Section(
                        course_id=course.id,
                        crn=parsed_section.crn,
                        section_code=parsed_section.section,
                        status=parsed_section.status,
                        credit_hours=parsed_section.credit_hours,
                        instructor=parsed_section.instructor,
                        part_of_term=parsed_section.part_of_term,
                        class_size=parsed_section.class_size,
                        seats_available=seats,
                        waitlist_count=waitlist,
                        # Schedule info
                        days=parsed_section.days,
                        start_time=parsed_section.start_time,
                        end_time=parsed_section.end_time,
                        building=parsed_section.building,
                        room=parsed_section.room,
                        campus=parsed_section.campus,
                    )
                    session.add(section)

                    # Track instructor
                    if parsed_section.instructor:
                        self._ensure_instructor(
                            session, parsed_section.instructor, instructor_cache
                        )

            session.commit()
            return schedule

    def _ensure_instructor(
        self,
        session: Session,
        name: str,
        cache: dict[str, Instructor]
    ) -> Instructor:
        """Ensure instructor exists in database, using cache for efficiency."""
        if name in cache:
            return cache[name]

        instructor = session.execute(
            select(Instructor).where(Instructor.name == name)
        ).scalar_one_or_none()

        if not instructor:
            instructor = Instructor(name=name)
            session.add(instructor)
            session.flush()

        cache[name] = instructor
        return instructor

    def import_pdf(
        self,
        pdf_path: str | Path,
        source_url: str = ""
    ) -> tuple[Schedule, ParseResult]:
        """
        Parse a PDF file and import it into the database.

        Returns:
            Tuple of (Schedule, ParseResult)
        """
        pdf_path = Path(pdf_path)

        # Calculate hash of the PDF for deduplication
        with open(pdf_path, 'rb') as f:
            source_hash = hashlib.sha256(f.read()).hexdigest()

        # Parse the PDF
        result = parse_uga_schedule(pdf_path, source_url)

        # Import into database
        schedule = self.import_schedule(
            result.schedule,
            source_hash=source_hash
        )

        return schedule, result

    def get_current_schedule(self, term: Optional[str] = None) -> Optional[Schedule]:
        """Get the current (most recent) schedule, optionally filtered by term."""
        with self.session_factory() as session:
            query = select(Schedule).where(Schedule.is_current == True)
            if term:
                query = query.where(Schedule.term == term)
            query = query.order_by(Schedule.parse_date.desc()).limit(1)
            return session.execute(query).scalar_one_or_none()

    def get_courses(
        self,
        schedule_id: Optional[int] = None,
        subject: Optional[str] = None,
        search: Optional[str] = None,
        has_availability: Optional[bool] = None,
        instructor: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Course]:
        """
        Query courses with various filters.

        Args:
            schedule_id: Filter by schedule (defaults to current)
            subject: Filter by subject code (e.g., "CSCI")
            search: Search in title, course code, or department
            has_availability: Filter by availability
            instructor: Filter by instructor name (partial match)
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of Course objects with sections loaded
        """
        with self.session_factory() as session:
            # Start with base query
            query = select(Course).options(selectinload(Course.sections))

            # Determine schedule
            if schedule_id is None:
                current = self.get_current_schedule()
                if current:
                    schedule_id = current.id

            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            # Apply filters
            if subject:
                query = query.where(Course.subject == subject.upper())

            if search:
                search_term = f"%{search}%"
                query = query.where(
                    or_(
                        Course.title.ilike(search_term),
                        Course.course_code.ilike(search_term),
                        Course.department.ilike(search_term),
                    )
                )

            if instructor:
                # Need to join with sections for instructor filter
                query = query.join(Section).where(
                    Section.instructor.ilike(f"%{instructor}%")
                ).distinct()

            # Order and paginate
            query = query.order_by(Course.subject, Course.course_number)
            query = query.limit(limit).offset(offset)

            courses = list(session.execute(query).scalars().all())

            # Filter by availability in Python (requires loaded sections)
            if has_availability is not None:
                courses = [c for c in courses if c.has_availability == has_availability]

            return courses

    def get_course_by_code(
        self,
        course_code: str,
        schedule_id: Optional[int] = None
    ) -> Optional[Course]:
        """Get a specific course by its code (e.g., 'CSCI 1301')."""
        with self.session_factory() as session:
            query = select(Course).options(selectinload(Course.sections))
            query = query.where(Course.course_code == course_code.upper())

            if schedule_id is None:
                current = self.get_current_schedule()
                if current:
                    schedule_id = current.id

            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            return session.execute(query).scalar_one_or_none()

    def get_section_by_crn(
        self,
        crn: str,
        schedule_id: Optional[int] = None
    ) -> Optional[Section]:
        """Get a specific section by CRN."""
        with self.session_factory() as session:
            query = (
                select(Section)
                .join(Course)
                .options(selectinload(Section.course))
                .where(Section.crn == crn)
            )

            if schedule_id is None:
                current = self.get_current_schedule()
                if current:
                    schedule_id = current.id

            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            return session.execute(query).scalar_one_or_none()

    def get_subjects(self, schedule_id: Optional[int] = None) -> list[str]:
        """Get list of all unique subject codes."""
        with self.session_factory() as session:
            query = select(Course.subject).distinct()

            if schedule_id is None:
                current = self.get_current_schedule()
                if current:
                    schedule_id = current.id

            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            query = query.order_by(Course.subject)
            return list(session.execute(query).scalars().all())

    def get_instructors(
        self,
        search: Optional[str] = None,
        limit: int = 100
    ) -> list[Instructor]:
        """Get instructors, optionally filtered by name search."""
        with self.session_factory() as session:
            query = select(Instructor)

            if search:
                query = query.where(Instructor.name.ilike(f"%{search}%"))

            query = query.order_by(Instructor.name).limit(limit)
            return list(session.execute(query).scalars().all())

    def get_stats(self, schedule_id: Optional[int] = None) -> dict:
        """Get statistics about the schedule."""
        with self.session_factory() as session:
            if schedule_id is None:
                current = self.get_current_schedule()
                if current:
                    schedule_id = current.id

            if not schedule_id:
                return {}

            # Get schedule info
            schedule = session.get(Schedule, schedule_id)
            if not schedule:
                return {}

            # Count available sections
            available_sections = session.execute(
                select(func.count(Section.id))
                .join(Course)
                .where(
                    Course.schedule_id == schedule_id,
                    Section.status == 'A',
                    Section.seats_available > 0
                )
            ).scalar()

            # Count total seats
            total_seats = session.execute(
                select(func.sum(Section.class_size))
                .join(Course)
                .where(Course.schedule_id == schedule_id)
            ).scalar() or 0

            available_seats = session.execute(
                select(func.sum(Section.seats_available))
                .join(Course)
                .where(
                    Course.schedule_id == schedule_id,
                    Section.seats_available > 0
                )
            ).scalar() or 0

            # Unique instructors
            instructor_count = session.execute(
                select(func.count(func.distinct(Section.instructor)))
                .join(Course)
                .where(
                    Course.schedule_id == schedule_id,
                    Section.instructor.isnot(None)
                )
            ).scalar()

            return {
                "term": schedule.term,
                "total_courses": schedule.total_courses,
                "total_sections": schedule.total_sections,
                "available_sections": available_sections,
                "total_seats": total_seats,
                "available_seats": available_seats,
                "instructor_count": instructor_count,
                "parse_date": schedule.parse_date.isoformat(),
            }


# Convenience function
def create_service() -> CourseService:
    """Create a CourseService instance with default configuration."""
    return CourseService()
