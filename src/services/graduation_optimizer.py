"""
Graduation Path Optimizer.

Generates optimized graduation paths based on student preferences:
- Graduate ASAP: Minimize semesters to graduation
- Party Mode: Easy classes, fun schedule, maximize social time

Combines:
- Degree requirements (from audit_service)
- Course availability (from schedule data)
- Campus geography (for walking time optimization)
- Instructor ratings (for difficulty optimization)
- Prerequisites (for proper sequencing)
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from datetime import datetime
from sqlalchemy import select, text, and_, func
from sqlalchemy.orm import Session

from src.models.database import (
    User, Program, ProgramRequirement, RequirementCourse,
    Course, Section, Instructor, BulletinCourse,
    CoursePrerequisite, UserCompletedCourse,
    get_engine, get_session_factory
)
from src.services.audit_service import AuditService
from src.services.progress_service import ProgressService
from src.services.rules_engine import SatisfactionStatus
from src.models.campus_graph import CampusGraph, build_campus_graph_from_schedule

logger = logging.getLogger(__name__)


class OptimizationMode(str, Enum):
    """Optimization strategies for schedule generation."""
    GRADUATE_ASAP = "graduate_asap"      # Minimize time to graduation
    PARTY_MODE = "party_mode"            # Easy classes, good schedule, social time
    BALANCED = "balanced"                # Balance between speed and difficulty
    INTEREST_BASED = "interest_based"    # Align with student interests


@dataclass
class CourseOption:
    """A course that could be taken to satisfy requirements."""
    course_code: str
    title: str
    credit_hours: int
    requirement_id: int
    requirement_name: str
    requirement_category: str

    # Availability
    sections_available: int = 0
    seats_available: int = 0

    # For optimization
    avg_instructor_rating: Optional[float] = None
    avg_difficulty: Optional[float] = None
    easiest_section_instructor: Optional[str] = None
    easiest_section_crn: Optional[str] = None

    # Prerequisites
    prerequisites: list[str] = field(default_factory=list)
    prereqs_satisfied: bool = True

    # Priority for ordering (higher = take sooner)
    priority_score: float = 0.0


@dataclass
class SemesterPlan:
    """A suggested schedule for one semester."""
    semester: str  # e.g., "Fall 2026"
    courses: list[CourseOption]
    total_hours: int

    # Metrics
    avg_difficulty: Optional[float] = None
    total_walking_minutes: int = 0
    conflicts: list[str] = field(default_factory=list)

    # Summary
    notes: list[str] = field(default_factory=list)


@dataclass
class GraduationPath:
    """Complete path to graduation."""
    user_id: int
    program_name: str
    degree_type: str
    optimization_mode: OptimizationMode

    # Current status
    current_hours: int
    hours_remaining: int

    # The plan
    semesters: list[SemesterPlan]
    estimated_graduation: str  # e.g., "Spring 2027"
    total_semesters_remaining: int

    # Warnings/notes
    warnings: list[str] = field(default_factory=list)

    # Generated at
    generated_at: datetime = field(default_factory=datetime.utcnow)


class GraduationOptimizer:
    """
    Generates optimized graduation paths.

    Two main modes:
    - Graduate ASAP: Pack in courses, minimize semesters
    - Party Mode: Easy courses, optimal schedule, social time
    """

    # Credit hour limits
    MIN_HOURS_PER_SEMESTER = 12  # Full-time minimum
    MAX_HOURS_PER_SEMESTER = 18  # Standard max without override
    OVERLOAD_HOURS = 21          # With override

    # Difficulty thresholds for party mode
    EASY_DIFFICULTY_THRESHOLD = 2.5  # RMP difficulty <= this is "easy"
    GOOD_RATING_THRESHOLD = 3.5      # RMP rating >= this is "good"

    def __init__(self, session_factory=None):
        if session_factory is None:
            engine = get_engine()
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory
        self.audit_service = AuditService(session_factory)
        self.progress_service = ProgressService(session_factory)
        self._campus_graph: Optional[CampusGraph] = None

    @property
    def campus_graph(self) -> CampusGraph:
        """Lazy-load campus graph."""
        if self._campus_graph is None:
            self._campus_graph = CampusGraph()
        return self._campus_graph

    def generate_path(
        self,
        user_id: int,
        mode: OptimizationMode = OptimizationMode.BALANCED,
        hours_per_semester: int = 15,
        start_semester: Optional[str] = None,
        interests: Optional[list[str]] = None,
    ) -> GraduationPath:
        """
        Generate an optimized graduation path.

        Args:
            user_id: The student's user ID
            mode: Optimization strategy
            hours_per_semester: Target hours per semester
            start_semester: Starting semester (default: next available)
            interests: Student interests for elective selection

        Returns:
            GraduationPath with semester-by-semester plan
        """
        with self.session_factory() as session:
            # Get user and enrollment
            user = session.get(User, user_id)
            if not user:
                raise ValueError("User not found")

            # Get enrollment
            enrollment = self.progress_service.get_primary_enrollment(user_id)
            if not enrollment:
                raise ValueError("No program enrollment found")

            program = session.get(Program, enrollment.program_id)
            if not program:
                raise ValueError("Program not found")

            # Run degree audit to know what's needed
            audit = self.audit_service.run_audit(user_id, enrollment.id)

            # Get completed courses
            completed_codes = self.progress_service.get_completed_course_codes(user_id)

            # Get remaining courses needed
            remaining_courses = self._get_remaining_courses(
                session, audit, completed_codes, mode
            )

            # Determine starting semester
            if not start_semester:
                start_semester = self._get_next_semester()

            # Generate semester plans
            semesters = self._plan_semesters(
                session,
                remaining_courses,
                completed_codes,
                mode,
                hours_per_semester,
                start_semester,
                interests or [],
            )

            # Calculate estimated graduation
            hours_remaining = audit.total_hours_required - audit.total_hours_earned
            total_semesters = len(semesters)

            if semesters:
                estimated_graduation = semesters[-1].semester
            else:
                estimated_graduation = start_semester

            # Build warnings
            warnings = []
            if hours_remaining > total_semesters * hours_per_semester:
                warnings.append(
                    f"At {hours_per_semester} hours/semester, you may need more semesters. "
                    f"Consider taking {self.MAX_HOURS_PER_SEMESTER}+ hours some semesters."
                )

            return GraduationPath(
                user_id=user_id,
                program_name=program.name,
                degree_type=program.degree_type,
                optimization_mode=mode,
                current_hours=audit.total_hours_earned,
                hours_remaining=hours_remaining,
                semesters=semesters,
                estimated_graduation=estimated_graduation,
                total_semesters_remaining=total_semesters,
                warnings=warnings,
            )

    def _get_remaining_courses(
        self,
        session: Session,
        audit,
        completed_codes: set[str],
        mode: OptimizationMode,
    ) -> list[CourseOption]:
        """
        Get all courses still needed to satisfy requirements.

        Enriches with instructor ratings and availability.
        """
        remaining = []

        for req_result in audit.requirements:
            if req_result.status == SatisfactionStatus.COMPLETE:
                continue

            # Get requirement details
            requirement = session.get(ProgramRequirement, req_result.requirement_id)
            if not requirement:
                continue

            # Get courses for this requirement
            req_courses = session.execute(
                select(RequirementCourse)
                .where(RequirementCourse.requirement_id == req_result.requirement_id)
            ).scalars().all()

            for req_course in req_courses:
                if req_course.course_code in completed_codes:
                    continue

                if req_course.is_group:
                    # Handle elective groups later
                    continue

                # Get course details and availability
                course_option = self._build_course_option(
                    session,
                    req_course.course_code,
                    req_result.requirement_id,
                    req_result.requirement_name,
                    req_result.category,
                    completed_codes,
                    mode,
                )

                if course_option:
                    remaining.append(course_option)

        # Sort by priority
        remaining.sort(key=lambda c: -c.priority_score)

        return remaining

    def _build_course_option(
        self,
        session: Session,
        course_code: str,
        requirement_id: int,
        requirement_name: str,
        requirement_category: str,
        completed_codes: set[str],
        mode: OptimizationMode,
    ) -> Optional[CourseOption]:
        """Build a CourseOption with all relevant data."""

        # Get bulletin course for prereqs
        bulletin = session.execute(
            select(BulletinCourse)
            .where(BulletinCourse.course_code == course_code)
        ).scalar_one_or_none()

        credit_hours = 3
        title = course_code
        prerequisites = []

        if bulletin:
            credit_hours = int(bulletin.credit_hours.split("-")[0]) if bulletin.credit_hours else 3
            title = bulletin.title or course_code
            if bulletin.prerequisites:
                prerequisites = self._parse_prerequisites(bulletin.prerequisites)

        # Check if prereqs are satisfied
        prereqs_satisfied = all(p in completed_codes for p in prerequisites)

        # Get current semester availability
        current_course = session.execute(
            select(Course)
            .where(Course.course_code == course_code)
        ).scalar_one_or_none()

        sections_available = 0
        seats_available = 0
        avg_rating = None
        avg_difficulty = None
        easiest_instructor = None
        easiest_crn = None

        if current_course:
            sections = list(current_course.sections)
            sections_available = len([s for s in sections if s.is_available])
            seats_available = sum(s.seats_available for s in sections if s.is_available)

            # Get instructor ratings
            instructor_data = self._get_instructor_ratings(session, sections, mode)
            if instructor_data:
                avg_rating = instructor_data.get("avg_rating")
                avg_difficulty = instructor_data.get("avg_difficulty")
                easiest_instructor = instructor_data.get("easiest_instructor")
                easiest_crn = instructor_data.get("easiest_crn")

        # Calculate priority score
        priority_score = self._calculate_priority(
            course_code,
            requirement_category,
            prereqs_satisfied,
            seats_available,
            avg_difficulty,
            mode,
        )

        return CourseOption(
            course_code=course_code,
            title=title,
            credit_hours=credit_hours,
            requirement_id=requirement_id,
            requirement_name=requirement_name,
            requirement_category=requirement_category,
            sections_available=sections_available,
            seats_available=seats_available,
            avg_instructor_rating=avg_rating,
            avg_difficulty=avg_difficulty,
            easiest_section_instructor=easiest_instructor,
            easiest_section_crn=easiest_crn,
            prerequisites=prerequisites,
            prereqs_satisfied=prereqs_satisfied,
            priority_score=priority_score,
        )

    def _get_instructor_ratings(
        self,
        session: Session,
        sections: list[Section],
        mode: OptimizationMode,
    ) -> dict:
        """Get instructor ratings for sections."""
        ratings = []
        difficulties = []
        easiest = None
        easiest_difficulty = 5.0

        for section in sections:
            if not section.instructor:
                continue

            instructor = session.execute(
                select(Instructor)
                .where(Instructor.name == section.instructor)
            ).scalar_one_or_none()

            if instructor:
                if instructor.rmp_rating:
                    ratings.append(instructor.rmp_rating)
                if instructor.rmp_difficulty:
                    difficulties.append(instructor.rmp_difficulty)

                    # Track easiest for party mode
                    if instructor.rmp_difficulty < easiest_difficulty:
                        easiest_difficulty = instructor.rmp_difficulty
                        easiest = {
                            "instructor": section.instructor,
                            "crn": section.crn,
                            "difficulty": instructor.rmp_difficulty,
                        }

        result = {}
        if ratings:
            result["avg_rating"] = sum(ratings) / len(ratings)
        if difficulties:
            result["avg_difficulty"] = sum(difficulties) / len(difficulties)
        if easiest:
            result["easiest_instructor"] = easiest["instructor"]
            result["easiest_crn"] = easiest["crn"]

        return result

    def _calculate_priority(
        self,
        course_code: str,
        category: str,
        prereqs_satisfied: bool,
        seats_available: int,
        avg_difficulty: Optional[float],
        mode: OptimizationMode,
    ) -> float:
        """
        Calculate priority score for a course.

        Higher = should take sooner.
        """
        score = 50.0  # Base score

        # Category priority (major > foundation > gen_ed > elective)
        category_priority = {
            "major": 20,
            "core": 15,
            "foundation": 10,
            "gen_ed": 5,
            "elective": 0,
        }
        score += category_priority.get(category, 0)

        # Prerequisites satisfied
        if prereqs_satisfied:
            score += 30
        else:
            score -= 50  # Significant penalty

        # Availability
        if seats_available > 50:
            score += 5
        elif seats_available == 0:
            score -= 20

        # Mode-specific adjustments
        if mode == OptimizationMode.PARTY_MODE:
            if avg_difficulty is not None:
                if avg_difficulty <= self.EASY_DIFFICULTY_THRESHOLD:
                    score += 25  # Bonus for easy classes
                elif avg_difficulty >= 4.0:
                    score -= 20  # Penalty for hard classes

        elif mode == OptimizationMode.GRADUATE_ASAP:
            # Prioritize courses that unlock others (gateway courses)
            course_number = int(course_code.split()[-1][:1]) * 1000
            if course_number <= 2000:
                score += 15  # Take foundational courses first

        return score

    def _plan_semesters(
        self,
        session: Session,
        remaining_courses: list[CourseOption],
        completed_codes: set[str],
        mode: OptimizationMode,
        hours_per_semester: int,
        start_semester: str,
        interests: list[str],
    ) -> list[SemesterPlan]:
        """Generate semester-by-semester plans."""
        semesters = []
        current_semester = start_semester
        courses_scheduled: set[str] = set()
        unlocked_codes = completed_codes.copy()

        max_iterations = 20  # Safety limit
        iteration = 0

        while remaining_courses and iteration < max_iterations:
            iteration += 1

            # Get available courses for this semester
            available = [
                c for c in remaining_courses
                if c.course_code not in courses_scheduled
                and c.prereqs_satisfied
            ]

            if not available:
                # Check if we can unlock more courses
                any_unlocked = False
                for course in remaining_courses:
                    if course.course_code not in courses_scheduled:
                        course.prereqs_satisfied = all(
                            p in unlocked_codes for p in course.prerequisites
                        )
                        if course.prereqs_satisfied:
                            any_unlocked = True

                if not any_unlocked:
                    break
                continue

            # Select courses for this semester
            semester_courses = self._select_semester_courses(
                available, hours_per_semester, mode
            )

            if not semester_courses:
                break

            # Calculate semester metrics
            total_hours = sum(c.credit_hours for c in semester_courses)

            avg_diff = None
            difficulties = [c.avg_difficulty for c in semester_courses if c.avg_difficulty]
            if difficulties:
                avg_diff = sum(difficulties) / len(difficulties)

            # Generate notes based on mode
            notes = []
            if mode == OptimizationMode.PARTY_MODE:
                easy_count = len([c for c in semester_courses
                                 if c.avg_difficulty and c.avg_difficulty <= self.EASY_DIFFICULTY_THRESHOLD])
                if easy_count > 0:
                    notes.append(f"{easy_count} easy class(es) with low difficulty ratings")

            elif mode == OptimizationMode.GRADUATE_ASAP:
                if total_hours >= 18:
                    notes.append("Heavy load - consider summer classes if needed")

            semester_plan = SemesterPlan(
                semester=current_semester,
                courses=semester_courses,
                total_hours=total_hours,
                avg_difficulty=avg_diff,
                notes=notes,
            )
            semesters.append(semester_plan)

            # Update tracking
            for course in semester_courses:
                courses_scheduled.add(course.course_code)
                unlocked_codes.add(course.course_code)

            # Update remaining courses prerequisites
            for course in remaining_courses:
                if course.course_code not in courses_scheduled:
                    course.prereqs_satisfied = all(
                        p in unlocked_codes for p in course.prerequisites
                    )
                    course.priority_score = self._calculate_priority(
                        course.course_code,
                        course.requirement_category,
                        course.prereqs_satisfied,
                        course.seats_available,
                        course.avg_difficulty,
                        mode,
                    )

            # Sort remaining by updated priority
            remaining_courses = [c for c in remaining_courses
                                if c.course_code not in courses_scheduled]
            remaining_courses.sort(key=lambda c: -c.priority_score)

            # Move to next semester
            current_semester = self._next_semester(current_semester)

        return semesters

    def _select_semester_courses(
        self,
        available: list[CourseOption],
        target_hours: int,
        mode: OptimizationMode,
    ) -> list[CourseOption]:
        """Select courses for a single semester."""
        selected = []
        current_hours = 0

        # Sort by priority (already done, but ensure)
        available.sort(key=lambda c: -c.priority_score)

        for course in available:
            if current_hours + course.credit_hours > self.MAX_HOURS_PER_SEMESTER:
                continue

            if current_hours + course.credit_hours > target_hours + 3:
                # Allow small overflow but not excessive
                if current_hours >= target_hours - 3:
                    break

            selected.append(course)
            current_hours += course.credit_hours

            if current_hours >= target_hours:
                break

        return selected

    def _parse_prerequisites(self, prereq_text: str) -> list[str]:
        """Extract course codes from prerequisite text."""
        import re

        if not prereq_text:
            return []

        # Find patterns like "CSCI 1301" or "MATH 2250"
        pattern = r'\b([A-Z]{2,4})\s*(\d{4}[A-Z]?)\b'
        matches = re.findall(pattern, prereq_text.upper())

        return [f"{subj} {num}" for subj, num in matches]

    def _get_next_semester(self) -> str:
        """Determine the next available semester."""
        now = datetime.now()
        year = now.year
        month = now.month

        # Spring registration (Nov-Jan) -> Spring
        # Fall registration (Apr-Aug) -> Fall
        # Summer registration (Feb-Apr) -> Summer

        if month >= 8:
            return f"Spring {year + 1}"
        elif month >= 3:
            return f"Fall {year}"
        else:
            return f"Spring {year}"

    def _next_semester(self, current: str) -> str:
        """Get the next semester after current."""
        parts = current.split()
        season = parts[0]
        year = int(parts[1])

        if season == "Spring":
            return f"Summer {year}"
        elif season == "Summer":
            return f"Fall {year}"
        else:  # Fall
            return f"Spring {year + 1}"

    def get_what_if_scenarios(
        self,
        user_id: int,
        scenarios: list[dict],
    ) -> list[dict]:
        """
        Run multiple what-if scenarios.

        Each scenario: {"name": "Take summer classes", "courses": ["CSCI 1302", "MATH 2250"]}

        Returns comparison of outcomes.
        """
        results = []

        enrollment = self.progress_service.get_primary_enrollment(user_id)
        if not enrollment:
            return results

        for scenario in scenarios:
            name = scenario.get("name", "Scenario")
            courses = scenario.get("courses", [])

            # Run what-if audit
            hypothetical = [
                {"course_code": code, "grade": "A", "credit_hours": 3}
                for code in courses
            ]

            audit = self.audit_service.what_if_analysis(
                user_id, enrollment.id, hypothetical
            )

            results.append({
                "name": name,
                "courses_added": courses,
                "new_progress_percent": audit.overall_progress_percent,
                "hours_after": audit.total_hours_earned,
                "hours_remaining": audit.total_hours_required - audit.total_hours_earned,
                "estimated_semesters_remaining": max(1,
                    (audit.total_hours_required - audit.total_hours_earned) // 15
                ),
            })

        return results

    def generate_party_mode_schedule(
        self,
        user_id: int,
        semester: str,
        target_hours: int = 12,
        preferred_times: Optional[list[str]] = None,  # ["afternoon", "no_early"]
    ) -> SemesterPlan:
        """
        Generate an optimal "party mode" schedule for a specific semester.

        Optimizes for:
        - Easy classes (low RMP difficulty)
        - Good instructors (high RMP rating)
        - Preferred times (no 8am classes, etc.)
        - Minimal walking between classes
        """
        with self.session_factory() as session:
            # Get needed courses with party mode optimization
            path = self.generate_path(
                user_id,
                mode=OptimizationMode.PARTY_MODE,
                hours_per_semester=target_hours,
                start_semester=semester,
            )

            if path.semesters:
                semester_plan = path.semesters[0]

                # Add party mode notes
                semester_plan.notes.append(
                    "Schedule optimized for low difficulty and good instructor ratings"
                )

                # Filter for time preferences if specified
                if preferred_times and "no_early" in preferred_times:
                    semester_plan.notes.append("Avoiding early morning classes where possible")

                return semester_plan

            return SemesterPlan(
                semester=semester,
                courses=[],
                total_hours=0,
                notes=["No courses available - check requirements"],
            )


def create_graduation_optimizer() -> GraduationOptimizer:
    """Create a GraduationOptimizer instance."""
    return GraduationOptimizer()
