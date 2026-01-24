"""
Course Linking Service.

Links schedule courses to bulletin courses and provides
graph-like queries for course relationships.

Designed to be easily extended with Neo4j later.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional
from sqlalchemy import select, func, and_, or_, text
from sqlalchemy.orm import Session, selectinload

from src.models.database import (
    Course, Section, BulletinCourse, Program, ProgramRequirement, RequirementCourse,
    CoursePrerequisite, CourseEquivalent, CourseUnlock, ScheduleBulletinLink,
    get_engine, get_session_factory, init_db
)
from src.services.prerequisite_parser import PrerequisiteParser

logger = logging.getLogger(__name__)


@dataclass
class CourseInfo:
    """Combined course info from schedule and bulletin."""
    code: str
    title: str
    description: Optional[str] = None
    prerequisites_text: Optional[str] = None
    prerequisites_structured: list = field(default_factory=list)
    credit_hours: Optional[str] = None
    semester_offered: Optional[str] = None
    # From schedule
    sections_available: int = 0
    total_seats: int = 0
    available_seats: int = 0
    instructors: list[str] = field(default_factory=list)


@dataclass
class RequirementStatus:
    """Status of a requirement for a student."""
    requirement_name: str
    category: str
    required_hours: Optional[int]
    completed_hours: int = 0
    in_progress_hours: int = 0
    remaining_hours: int = 0
    is_satisfied: bool = False
    completed_courses: list[str] = field(default_factory=list)
    remaining_courses: list[str] = field(default_factory=list)
    available_courses: list[str] = field(default_factory=list)  # Available this semester


@dataclass
class DegreeProgress:
    """Overall degree progress for a student."""
    program_name: str
    degree_type: str
    total_hours_required: int
    total_hours_completed: int
    total_hours_in_progress: int
    overall_progress: float  # 0-1
    requirements: list[RequirementStatus] = field(default_factory=list)
    next_recommended: list[str] = field(default_factory=list)


class CourseLinker:
    """
    Service for linking and querying course relationships.

    Provides graph-like queries using PostgreSQL, designed to be
    easily extended with Neo4j for complex graph operations.
    """

    def __init__(self, session_factory=None):
        """Initialize the linker."""
        if session_factory is None:
            engine = get_engine()
            init_db(engine)
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory
        self.prereq_parser = PrerequisiteParser(session_factory)

    def link_schedule_to_bulletin(self, schedule_id: int = None) -> dict:
        """
        Link all schedule courses to their bulletin counterparts.

        Args:
            schedule_id: Optional schedule ID (defaults to current)

        Returns:
            Statistics dict
        """
        stats = {
            "courses_processed": 0,
            "exact_matches": 0,
            "no_match": 0,
        }

        with self.session_factory() as session:
            # Get schedule courses
            query = select(Course).options(selectinload(Course.sections))
            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)
            else:
                # Get current schedule (most recent if multiple)
                from src.models.database import Schedule
                current = session.execute(
                    select(Schedule).where(Schedule.is_current == True)
                    .order_by(Schedule.parse_date.desc()).limit(1)
                ).scalar_one_or_none()
                if current:
                    query = query.where(Course.schedule_id == current.id)

            courses = session.execute(query).scalars().all()

            for course in courses:
                stats["courses_processed"] += 1

                # Try exact match on course_code
                bulletin = session.execute(
                    select(BulletinCourse).where(
                        BulletinCourse.course_code == course.course_code
                    )
                ).scalar_one_or_none()

                if bulletin:
                    stats["exact_matches"] += 1

                    # Create or update link
                    existing_link = session.execute(
                        select(ScheduleBulletinLink).where(
                            ScheduleBulletinLink.schedule_course_id == course.id
                        )
                    ).scalar_one_or_none()

                    if existing_link:
                        existing_link.bulletin_course_id = bulletin.id
                        existing_link.confidence = 1.0
                        existing_link.link_method = "exact"
                    else:
                        link = ScheduleBulletinLink(
                            schedule_course_id=course.id,
                            bulletin_course_id=bulletin.id,
                            course_code=course.course_code,
                            confidence=1.0,
                            link_method="exact",
                        )
                        session.add(link)

                    # Copy description to schedule course if missing
                    if not course.description and bulletin.description:
                        course.description = bulletin.description
                    if not course.prerequisites and bulletin.prerequisites:
                        course.prerequisites = bulletin.prerequisites
                else:
                    stats["no_match"] += 1
                    # Create link with just course_code (no bulletin match)
                    existing_link = session.execute(
                        select(ScheduleBulletinLink).where(
                            ScheduleBulletinLink.schedule_course_id == course.id
                        )
                    ).scalar_one_or_none()

                    if not existing_link:
                        link = ScheduleBulletinLink(
                            schedule_course_id=course.id,
                            bulletin_course_id=None,
                            course_code=course.course_code,
                            confidence=0.0,
                            link_method="none",
                        )
                        session.add(link)

            session.commit()

        return stats

    def get_course_info(self, course_code: str, schedule_id: int = None) -> Optional[CourseInfo]:
        """
        Get combined course info from schedule and bulletin.

        Args:
            course_code: Course code (e.g., "CSCI 1301")
            schedule_id: Optional schedule ID

        Returns:
            CourseInfo or None
        """
        with self.session_factory() as session:
            # Get bulletin course
            bulletin = session.execute(
                select(BulletinCourse).where(BulletinCourse.course_code == course_code)
            ).scalar_one_or_none()

            # Get schedule course
            query = select(Course).options(selectinload(Course.sections))
            query = query.where(Course.course_code == course_code)
            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)

            schedule_course = session.execute(query).scalar_one_or_none()

            if not bulletin and not schedule_course:
                return None

            info = CourseInfo(
                code=course_code,
                title=bulletin.title if bulletin else (schedule_course.title if schedule_course else "Unknown"),
            )

            # Fill from bulletin
            if bulletin:
                info.description = bulletin.description
                info.prerequisites_text = bulletin.prerequisites
                info.credit_hours = bulletin.credit_hours
                info.semester_offered = bulletin.semester_offered

            # Fill from schedule
            if schedule_course:
                info.sections_available = len([s for s in schedule_course.sections if s.is_available])
                info.total_seats = sum(s.class_size for s in schedule_course.sections)
                info.available_seats = sum(max(0, s.seats_available) for s in schedule_course.sections)
                info.instructors = list(set(
                    s.instructor for s in schedule_course.sections if s.instructor
                ))

            # Get structured prerequisites
            info.prerequisites_structured = self.prereq_parser.get_prerequisites_for(course_code)

            return info

    def get_prerequisites(self, course_code: str) -> list[dict]:
        """Get prerequisites for a course in structured format."""
        return self.prereq_parser.get_prerequisites_for(course_code)

    def get_unlocked_courses(self, course_code: str) -> list[dict]:
        """Get courses unlocked by completing a course."""
        return self.prereq_parser.get_courses_unlocked_by(course_code)

    def get_equivalent_courses(self, course_code: str) -> list[str]:
        """Get equivalent courses for a course."""
        with self.session_factory() as session:
            # Get equivalents in both directions
            equivs = session.execute(
                select(CourseEquivalent).where(
                    or_(
                        CourseEquivalent.course_code == course_code,
                        CourseEquivalent.equivalent_code == course_code,
                    )
                )
            ).scalars().all()

            result = set()
            for e in equivs:
                if e.course_code != course_code:
                    result.add(e.course_code)
                if e.equivalent_code != course_code:
                    result.add(e.equivalent_code)

            return list(result)

    def can_take_course(self, course_code: str, completed_courses: list[str]) -> dict:
        """
        Check if a student can take a course based on completed courses.

        Args:
            course_code: Course to check
            completed_courses: List of completed course codes

        Returns:
            Dict with 'can_take', 'missing_prerequisites', 'satisfied_groups'
        """
        with self.session_factory() as session:
            prereqs = session.execute(
                select(CoursePrerequisite)
                .where(CoursePrerequisite.course_code == course_code)
            ).scalars().all()

            if not prereqs:
                return {
                    "can_take": True,
                    "missing_prerequisites": [],
                    "satisfied_groups": [],
                }

            # Get equivalents for completed courses
            completed_with_equivs = set(completed_courses)
            for cc in completed_courses:
                equivs = self.get_equivalent_courses(cc)
                completed_with_equivs.update(equivs)

            # Group prerequisites by group_id
            groups = {}
            for p in prereqs:
                if p.group_id not in groups:
                    groups[p.group_id] = []
                groups[p.group_id].append(p.prerequisite_code)

            # Check each group (need one from each group to be satisfied)
            satisfied_groups = []
            missing_groups = []

            for group_id, courses in groups.items():
                # OR within group - need at least one
                if any(c in completed_with_equivs for c in courses):
                    satisfied_groups.append({
                        "group_id": group_id,
                        "options": courses,
                        "satisfied_by": [c for c in courses if c in completed_with_equivs],
                    })
                else:
                    missing_groups.append({
                        "group_id": group_id,
                        "options": courses,
                    })

            return {
                "can_take": len(missing_groups) == 0,
                "missing_prerequisites": missing_groups,
                "satisfied_groups": satisfied_groups,
            }

    def get_available_courses(self, completed_courses: list[str], schedule_id: int = None) -> list[dict]:
        """
        Get courses a student can take this semester based on completed courses.

        Args:
            completed_courses: List of completed course codes
            schedule_id: Optional schedule ID

        Returns:
            List of available courses with availability info
        """
        available = []

        with self.session_factory() as session:
            # Get all courses from current schedule
            query = select(Course).options(selectinload(Course.sections))
            if schedule_id:
                query = query.where(Course.schedule_id == schedule_id)
            else:
                from src.models.database import Schedule
                current = session.execute(
                    select(Schedule).where(Schedule.is_current == True)
                    .order_by(Schedule.parse_date.desc()).limit(1)
                ).scalar_one_or_none()
                if current:
                    query = query.where(Course.schedule_id == current.id)

            courses = session.execute(query).scalars().all()

            for course in courses:
                # Skip if already completed
                if course.course_code in completed_courses:
                    continue

                # Check if can take
                eligibility = self.can_take_course(course.course_code, completed_courses)

                if eligibility["can_take"]:
                    available.append({
                        "code": course.course_code,
                        "title": course.title,
                        "sections_available": len([s for s in course.sections if s.is_available]),
                        "total_seats": sum(s.class_size for s in course.sections),
                        "available_seats": sum(max(0, s.seats_available) for s in course.sections),
                    })

        # Sort by available seats (descending)
        available.sort(key=lambda x: x["available_seats"], reverse=True)

        return available

    def check_degree_progress(
        self,
        program_id: int,
        completed_courses: list[str],
        in_progress_courses: list[str] = None
    ) -> DegreeProgress:
        """
        Check a student's progress toward a degree.

        Args:
            program_id: Database ID of the program
            completed_courses: List of completed course codes
            in_progress_courses: List of courses currently taking

        Returns:
            DegreeProgress object
        """
        if in_progress_courses is None:
            in_progress_courses = []

        with self.session_factory() as session:
            program = session.execute(
                select(Program)
                .options(
                    selectinload(Program.requirements)
                    .selectinload(ProgramRequirement.courses)
                )
                .where(Program.id == program_id)
            ).scalar_one_or_none()

            if not program:
                raise ValueError(f"Program {program_id} not found")

            # Get equivalents for all completed courses
            all_completed = set(completed_courses)
            for cc in completed_courses:
                equivs = self.get_equivalent_courses(cc)
                all_completed.update(equivs)

            all_in_progress = set(in_progress_courses)

            progress = DegreeProgress(
                program_name=program.name,
                degree_type=program.degree_type,
                total_hours_required=program.total_hours or 120,
                total_hours_completed=0,
                total_hours_in_progress=0,
                overall_progress=0.0,
            )

            # Check each requirement
            for req in program.requirements:
                req_status = RequirementStatus(
                    requirement_name=req.name,
                    category=req.category,
                    required_hours=req.required_hours,
                )

                for req_course in req.courses:
                    code = req_course.course_code
                    hours = req_course.credit_hours or 3

                    if code in all_completed or any(code.startswith(c.split()[0]) for c in all_completed if code in all_completed):
                        req_status.completed_courses.append(code)
                        req_status.completed_hours += hours
                    elif code in all_in_progress:
                        req_status.in_progress_hours += hours
                    else:
                        req_status.remaining_courses.append(code)

                        # Check if available this semester
                        eligibility = self.can_take_course(code, list(all_completed))
                        if eligibility["can_take"]:
                            req_status.available_courses.append(code)

                # Calculate remaining
                if req.required_hours:
                    req_status.remaining_hours = max(
                        0,
                        req.required_hours - req_status.completed_hours - req_status.in_progress_hours
                    )
                    req_status.is_satisfied = req_status.completed_hours >= req.required_hours

                progress.requirements.append(req_status)
                progress.total_hours_completed += req_status.completed_hours
                progress.total_hours_in_progress += req_status.in_progress_hours

            # Calculate overall progress
            if progress.total_hours_required > 0:
                progress.overall_progress = min(
                    1.0,
                    progress.total_hours_completed / progress.total_hours_required
                )

            # Recommend next courses
            progress.next_recommended = self._recommend_next_courses(
                progress.requirements,
                list(all_completed),
            )

            return progress

    def _recommend_next_courses(
        self,
        requirements: list[RequirementStatus],
        completed: list[str],
        max_recommendations: int = 5
    ) -> list[str]:
        """Recommend next courses based on unsatisfied requirements."""
        recommendations = []

        # Prioritize unsatisfied requirements
        unsatisfied = [r for r in requirements if not r.is_satisfied]
        unsatisfied.sort(key=lambda r: r.remaining_hours or 0, reverse=True)

        for req in unsatisfied:
            for course in req.available_courses:
                if course not in recommendations and course not in completed:
                    recommendations.append(course)
                    if len(recommendations) >= max_recommendations:
                        return recommendations

        return recommendations

    def get_prerequisite_chain(self, course_code: str, max_depth: int = 10) -> dict:
        """
        Get the full prerequisite chain for a course (recursive).

        Uses a recursive CTE in PostgreSQL for efficiency.

        Args:
            course_code: Course to get chain for
            max_depth: Maximum recursion depth

        Returns:
            Tree structure of prerequisites
        """
        with self.session_factory() as session:
            # Use recursive CTE
            cte_query = text("""
                WITH RECURSIVE prereq_chain AS (
                    -- Base case
                    SELECT
                        course_code,
                        prerequisite_code,
                        group_id,
                        1 as depth
                    FROM course_prerequisites
                    WHERE course_code = :course_code

                    UNION ALL

                    -- Recursive case
                    SELECT
                        cp.course_code,
                        cp.prerequisite_code,
                        cp.group_id,
                        pc.depth + 1
                    FROM course_prerequisites cp
                    JOIN prereq_chain pc ON cp.course_code = pc.prerequisite_code
                    WHERE pc.depth < :max_depth
                )
                SELECT DISTINCT course_code, prerequisite_code, group_id, depth
                FROM prereq_chain
                ORDER BY depth, course_code, group_id
            """)

            try:
                result = session.execute(
                    cte_query,
                    {"course_code": course_code, "max_depth": max_depth}
                ).fetchall()
            except Exception:
                # Table might not exist yet
                return {"course": course_code, "prerequisites": []}

            # Build tree structure
            return self._build_prereq_tree(course_code, result)

    def _build_prereq_tree(self, course_code: str, rows: list) -> dict:
        """Build a tree structure from prerequisite rows."""
        tree = {"course": course_code, "prerequisites": []}

        # Find direct prerequisites
        direct = [r for r in rows if r[0] == course_code]

        # Group by group_id
        groups = {}
        for row in direct:
            prereq = row[1]
            group_id = row[2]
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(prereq)

        for group_id, prereqs in sorted(groups.items()):
            if len(prereqs) == 1:
                # Single prerequisite
                subtree = self._build_prereq_tree(prereqs[0], rows)
                tree["prerequisites"].append(subtree)
            else:
                # OR group
                tree["prerequisites"].append({
                    "type": "OR",
                    "options": [
                        self._build_prereq_tree(p, rows)
                        for p in prereqs
                    ]
                })

        return tree


def create_linker() -> CourseLinker:
    """Create a CourseLinker instance."""
    return CourseLinker()


# CLI helper
if __name__ == "__main__":
    import sys
    import json

    logging.basicConfig(level=logging.INFO)

    linker = CourseLinker()

    if len(sys.argv) > 1:
        course = sys.argv[1]
        print(f"Getting info for {course}...")

        info = linker.get_course_info(course)
        if info:
            print(f"Title: {info.title}")
            print(f"Credits: {info.credit_hours}")
            print(f"Prerequisites: {info.prerequisites_text}")
            print(f"Structured: {json.dumps(info.prerequisites_structured, indent=2)}")
            print(f"Sections: {info.sections_available}")
            print(f"Seats: {info.available_seats}/{info.total_seats}")
        else:
            print("Course not found")
    else:
        print("Usage: python -m src.services.course_linker COURSE_CODE")
