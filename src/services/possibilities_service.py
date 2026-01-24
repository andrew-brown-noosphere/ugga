"""
Course Possibilities Service.

Computes which courses a student can take this semester based on:
- Prerequisites met (given completed courses)
- Current semester availability (seats available)
- Plan type prioritization (fast-track, specialist, etc.)
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from sqlalchemy import select, and_
from sqlalchemy.orm import Session, selectinload

from src.models.database import (
    CoursePrerequisite, CourseUnlock, Course, Section, Schedule,
    Program, ProgramRequirement, RequirementCourse,
    get_engine, get_session_factory
)


class GoalType(str, Enum):
    FAST_TRACK = "fast-track"
    SPECIALIST = "specialist"
    WELL_ROUNDED = "well-rounded"
    FLEXIBLE = "flexible"


@dataclass
class PossibilitySection:
    """Section data for a course possibility."""
    crn: str
    instructor: Optional[str]
    days: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    building: Optional[str]
    room: Optional[str]
    seats_available: int
    class_size: int


@dataclass
class CoursePossibility:
    """A course that the student can potentially take."""
    course_code: str
    title: str
    credit_hours: int
    category: str  # foundation, major, elective, gen_ed
    requirement_name: str

    # Availability data
    total_sections: int
    available_sections: int
    total_seats: int
    available_seats: int

    # Prerequisite status
    prerequisites_met: bool
    missing_prerequisites: list[str] = field(default_factory=list)

    # Priority scoring
    priority_score: float = 0.0
    priority_reason: str = ""

    # Section details for calendar
    sections: list[PossibilitySection] = field(default_factory=list)


@dataclass
class PossibilitiesResult:
    """Result of computing course possibilities."""
    possibilities: list[CoursePossibility]
    total_available: int
    total_eligible: int  # Prerequisites met
    filters_applied: dict


class PossibilitiesService:
    """Service for computing course possibilities for a student."""

    def __init__(self, session_factory=None):
        if session_factory is None:
            engine = get_engine()
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    def get_possibilities(
        self,
        program_id: int,
        goal: GoalType,
        completed_courses: Optional[list[str]] = None,
        limit: int = 50,
    ) -> PossibilitiesResult:
        """
        Compute course possibilities for a student.

        Args:
            program_id: The degree program ID
            goal: The student's goal type
            completed_courses: List of completed course codes (empty for now)
            limit: Maximum courses to return

        Returns:
            PossibilitiesResult with prioritized course list
        """
        completed = set(c.upper() for c in (completed_courses or []))

        with self.session_factory() as session:
            # Step 1: Get all courses from program requirements
            program_courses = self._get_program_courses(session, program_id)

            if not program_courses:
                return PossibilitiesResult(
                    possibilities=[],
                    total_available=0,
                    total_eligible=0,
                    filters_applied={"program_id": program_id, "goal": goal.value}
                )

            # Step 2: Get current semester availability in bulk
            course_codes = [c["course_code"] for c in program_courses]
            availability_map = self._get_availability_map(session, course_codes)

            # Step 3: Get prerequisite data in bulk
            prereq_map = self._get_prerequisite_map(session, course_codes)

            # Step 4: Get which courses are prerequisites for others (for unlock scoring)
            unlock_value_map = self._get_unlock_value_map(session, course_codes)

            # Step 5: Build possibilities with eligibility check
            possibilities = []
            for course_info in program_courses:
                code = course_info["course_code"]

                # Skip completed courses
                if code in completed:
                    continue

                # Check availability
                avail = availability_map.get(code)
                if not avail or avail["available_seats"] <= 0:
                    continue  # Not offered or full

                # Check prerequisites
                prereqs = prereq_map.get(code, [])
                prereqs_met, missing = self._check_prerequisites(prereqs, completed)

                if not prereqs_met:
                    continue  # Prerequisites not met

                # Build sections list
                sections = [
                    PossibilitySection(
                        crn=s["crn"],
                        instructor=s["instructor"],
                        days=s["days"],
                        start_time=s["start_time"],
                        end_time=s["end_time"],
                        building=s["building"],
                        room=s["room"],
                        seats_available=s["seats_available"],
                        class_size=s["class_size"],
                    )
                    for s in avail.get("sections", [])
                ]

                # Build possibility
                possibility = CoursePossibility(
                    course_code=code,
                    title=course_info.get("title", ""),
                    credit_hours=course_info.get("credit_hours", 3),
                    category=course_info.get("category", "other"),
                    requirement_name=course_info.get("requirement_name", ""),
                    total_sections=avail.get("total_sections", 0),
                    available_sections=avail.get("available_sections", 0),
                    total_seats=avail.get("total_seats", 0),
                    available_seats=avail.get("available_seats", 0),
                    prerequisites_met=prereqs_met,
                    missing_prerequisites=missing,
                    sections=sections,
                )

                # Calculate priority score based on goal
                possibility.priority_score, possibility.priority_reason = \
                    self._calculate_priority(possibility, goal, unlock_value_map)

                possibilities.append(possibility)

            # Step 6: Sort by priority score
            possibilities.sort(key=lambda p: -p.priority_score)

            return PossibilitiesResult(
                possibilities=possibilities[:limit],
                total_available=len(possibilities),
                total_eligible=len(possibilities),
                filters_applied={
                    "program_id": program_id,
                    "goal": goal.value,
                    "completed_courses_count": len(completed),
                }
            )

    def _get_program_courses(self, session: Session, program_id: int) -> list[dict]:
        """Get all courses from a program's requirements."""
        courses = []

        query = (
            select(ProgramRequirement)
            .options(selectinload(ProgramRequirement.courses))
            .where(ProgramRequirement.program_id == program_id)
            .order_by(ProgramRequirement.display_order)
        )
        requirements = session.execute(query).scalars().all()

        seen_codes = set()
        for req in requirements:
            for rc in req.courses:
                if rc.is_group:
                    continue  # Skip group placeholders
                if rc.course_code in seen_codes:
                    continue  # Dedupe
                seen_codes.add(rc.course_code)
                courses.append({
                    "course_code": rc.course_code,
                    "title": rc.title or "",
                    "credit_hours": rc.credit_hours or 3,
                    "category": req.category,
                    "requirement_name": req.name,
                })

        return courses

    def _get_availability_map(
        self, session: Session, course_codes: list[str]
    ) -> dict[str, dict]:
        """Bulk fetch availability for courses from current schedule."""
        if not course_codes:
            return {}

        # Get current schedule
        current_schedule = session.execute(
            select(Schedule)
            .where(Schedule.is_current == True)
            .order_by(Schedule.parse_date.desc())
            .limit(1)
        ).scalar_one_or_none()

        if not current_schedule:
            return {}

        # Query sections for these courses
        query = (
            select(Course, Section)
            .join(Section, Section.course_id == Course.id)
            .where(
                and_(
                    Course.schedule_id == current_schedule.id,
                    Course.course_code.in_(course_codes),
                    Section.status == 'A',
                )
            )
        )
        results = session.execute(query).all()

        # Aggregate by course
        availability: dict[str, dict] = {}
        for course, section in results:
            code = course.course_code
            if code not in availability:
                availability[code] = {
                    "total_sections": 0,
                    "available_sections": 0,
                    "total_seats": 0,
                    "available_seats": 0,
                    "sections": [],
                }

            availability[code]["total_sections"] += 1
            availability[code]["total_seats"] += section.class_size

            if section.seats_available > 0:
                availability[code]["available_sections"] += 1
                availability[code]["available_seats"] += section.seats_available

            # Include section details for calendar
            availability[code]["sections"].append({
                "crn": section.crn,
                "instructor": section.instructor,
                "days": section.days,
                "start_time": section.start_time,
                "end_time": section.end_time,
                "building": section.building,
                "room": section.room,
                "seats_available": section.seats_available,
                "class_size": section.class_size,
            })

        return availability

    def _get_prerequisite_map(
        self, session: Session, course_codes: list[str]
    ) -> dict[str, list[dict]]:
        """Bulk fetch prerequisites for courses."""
        if not course_codes:
            return {}

        query = (
            select(CoursePrerequisite)
            .where(CoursePrerequisite.course_code.in_(course_codes))
            .order_by(CoursePrerequisite.group_id)
        )
        prereqs = session.execute(query).scalars().all()

        # Group by course
        prereq_map: dict[str, list[dict]] = {}
        for p in prereqs:
            if p.course_code not in prereq_map:
                prereq_map[p.course_code] = []
            prereq_map[p.course_code].append({
                "prerequisite_code": p.prerequisite_code,
                "group_id": p.group_id,
                "min_grade": p.min_grade,
            })

        return prereq_map

    def _get_unlock_value_map(
        self, session: Session, course_codes: list[str]
    ) -> dict[str, int]:
        """
        Calculate how many courses each course unlocks.

        Courses that are prerequisites for many others have higher unlock value.
        """
        if not course_codes:
            return {}

        # Count how many courses each code is a prerequisite for
        query = (
            select(CoursePrerequisite.prerequisite_code)
            .where(CoursePrerequisite.prerequisite_code.in_(course_codes))
        )
        results = session.execute(query).all()

        unlock_counts: dict[str, int] = {}
        for (prereq_code,) in results:
            unlock_counts[prereq_code] = unlock_counts.get(prereq_code, 0) + 1

        return unlock_counts

    def _check_prerequisites(
        self, prereqs: list[dict], completed: set[str]
    ) -> tuple[bool, list[str]]:
        """
        Check if prerequisites are met.

        Prerequisites with same group_id are OR alternatives.
        Different group_ids must ALL be satisfied.
        """
        if not prereqs:
            return True, []

        # Group by group_id
        groups: dict[int, list[str]] = {}
        for p in prereqs:
            gid = p["group_id"]
            if gid not in groups:
                groups[gid] = []
            groups[gid].append(p["prerequisite_code"])

        # Check each group - at least one course per group must be completed
        missing = []
        for gid, alternatives in groups.items():
            if not any(alt in completed for alt in alternatives):
                # None of the alternatives completed
                missing.append(alternatives[0])  # Report first alternative as missing

        return len(missing) == 0, missing

    def _calculate_priority(
        self, possibility: CoursePossibility,
        goal: GoalType,
        unlock_value_map: dict[str, int],
    ) -> tuple[float, str]:
        """Calculate priority score based on goal type."""
        score = 50.0  # Base score
        reasons = []

        category = possibility.category.lower()
        total_seats = max(possibility.total_seats, 1)
        fill_rate = 1 - (possibility.available_seats / total_seats)
        unlock_value = unlock_value_map.get(possibility.course_code, 0)

        if goal == GoalType.FAST_TRACK:
            # Prioritize: foundation courses, courses that unlock chains, filling fast
            if category in ["foundation", "core"]:
                score += 30
                reasons.append("Foundation/core course")
            elif category == "major":
                score += 20
                reasons.append("Major requirement")

            # Courses that unlock many others are valuable for fast-track
            if unlock_value >= 3:
                score += 25
                reasons.append(f"Unlocks {unlock_value}+ courses")
            elif unlock_value >= 1:
                score += 15
                reasons.append("Unlocks advanced courses")

            if fill_rate > 0.8:
                score += 15
                reasons.append("Filling fast")

        elif goal == GoalType.SPECIALIST:
            # Prioritize: major courses, depth over breadth
            if category == "major":
                score += 40
                reasons.append("Major requirement")
            elif category == "core":
                score += 30
                reasons.append("Core course")
            elif category == "foundation":
                score += 20
                reasons.append("Foundation for specialization")

            # Still value courses that unlock depth
            if unlock_value >= 2:
                score += 10
                reasons.append("Enables deeper study")

        elif goal == GoalType.WELL_ROUNDED:
            # Prioritize: balance across categories, gen-ed variety
            if category == "gen_ed":
                score += 30
                reasons.append("Broadens knowledge")
            elif category == "elective":
                score += 25
                reasons.append("Exploration opportunity")
            elif category in ["foundation", "core"]:
                score += 20
                reasons.append("Essential foundation")
            elif category == "major":
                score += 15
                reasons.append("Major requirement")

        else:  # FLEXIBLE
            # All courses similar priority, sort by availability
            if possibility.available_seats > 50:
                score += 20
                reasons.append("Good availability")
            elif possibility.available_seats > 20:
                score += 10
                reasons.append("Moderate availability")

            # Slight preference for core courses
            if category in ["foundation", "core", "major"]:
                score += 10
                reasons.append(f"{category.title()} course")

        # Universal adjustments
        if fill_rate > 0.9:
            score += 10
            reasons.append("Register soon")

        reason = "; ".join(reasons) if reasons else "Available this semester"
        return score, reason


def create_possibilities_service() -> PossibilitiesService:
    """Create a PossibilitiesService instance with default configuration."""
    return PossibilitiesService()
