"""
Rules Engine for Degree Requirement Evaluation.

Evaluates complex requirements like:
- course_list: Specific required courses
- hours_from_pool: X hours from specified courses/subjects/levels
- gpa_minimum: GPA requirements for subsets of courses
- course_level: Upper division hour requirements
- exclusion: Courses that can't count if others taken

Uses a best-fit allocation algorithm to optimally assign
completed courses to requirements.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.models.database import (
    UserCompletedCourse, UserProgramEnrollment, Program,
    ProgramRequirement, RequirementCourse, RequirementRule,
    get_engine, get_session_factory
)
from src.services.progress_service import GRADE_POINTS, PASSING_GRADES


class SatisfactionStatus(str, Enum):
    INCOMPLETE = "incomplete"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"


@dataclass
class CourseApplication:
    """Records which course was applied to which requirement."""
    course_code: str
    grade: Optional[str]  # Can be None for privacy
    credit_hours: int
    is_passing: bool


@dataclass
class RequirementResult:
    """Result of evaluating a single requirement."""
    requirement_id: int
    requirement_name: str
    category: str

    status: SatisfactionStatus
    hours_required: Optional[int]
    hours_satisfied: int
    courses_required: Optional[int]
    courses_satisfied: int

    # For GPA requirements
    gpa_required: Optional[float] = None
    gpa_achieved: Optional[float] = None

    # Courses that were applied to this requirement
    courses_applied: list[CourseApplication] = field(default_factory=list)

    # Remaining courses needed
    remaining_courses: list[str] = field(default_factory=list)

    # Human-readable description
    description: str = ""

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.hours_required and self.hours_required > 0:
            return min(100, (self.hours_satisfied / self.hours_required) * 100)
        if self.courses_required and self.courses_required > 0:
            return min(100, (self.courses_satisfied / self.courses_required) * 100)
        if self.gpa_required:
            if self.gpa_achieved and self.gpa_achieved >= self.gpa_required:
                return 100
            return 0
        return 0 if self.status == SatisfactionStatus.INCOMPLETE else 100


@dataclass
class DegreeAuditResult:
    """Complete degree audit result."""
    program_id: int
    program_name: str
    degree_type: str

    overall_status: SatisfactionStatus
    overall_progress_percent: float

    total_hours_required: int
    total_hours_earned: int
    cumulative_gpa: Optional[float]

    requirements: list[RequirementResult]

    # Suggestions for next steps
    recommended_next_courses: list[str] = field(default_factory=list)


class RulesEngine:
    """Engine for evaluating degree requirements against completed courses."""

    def __init__(self, session_factory=None):
        if session_factory is None:
            engine = get_engine()
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory

    def run_audit(
        self,
        user_id: int,
        enrollment_id: int,
    ) -> DegreeAuditResult:
        """
        Run a complete degree audit for a user's program enrollment.

        Uses best-fit allocation to optimally assign courses to requirements.
        """
        with self.session_factory() as session:
            # Get enrollment and program
            enrollment = session.get(UserProgramEnrollment, enrollment_id)
            if not enrollment or enrollment.user_id != user_id:
                raise ValueError("Invalid enrollment")

            program = session.get(Program, enrollment.program_id)
            if not program:
                raise ValueError("Program not found")

            # Get all completed courses
            completed_courses = self._get_completed_courses(session, user_id)

            # Get program requirements with courses and rules
            requirements = self._get_program_requirements(session, program.id)

            # Run best-fit allocation
            results, used_courses = self._evaluate_requirements(
                requirements, completed_courses
            )

            # Calculate overall progress
            total_hours_required = sum(
                r.hours_required or 0 for r in results
            )
            total_hours_satisfied = sum(r.hours_satisfied for r in results)

            # Use program total hours if available
            if program.total_hours:
                total_hours_required = program.total_hours

            overall_progress = 0
            if total_hours_required > 0:
                overall_progress = min(100, (total_hours_satisfied / total_hours_required) * 100)

            # Determine overall status
            all_complete = all(r.status == SatisfactionStatus.COMPLETE for r in results)
            any_progress = any(r.status != SatisfactionStatus.INCOMPLETE for r in results)

            if all_complete:
                overall_status = SatisfactionStatus.COMPLETE
            elif any_progress:
                overall_status = SatisfactionStatus.IN_PROGRESS
            else:
                overall_status = SatisfactionStatus.INCOMPLETE

            # Get recommended next courses
            recommended = self._get_recommended_courses(results, completed_courses)

            # Calculate cumulative GPA
            cumulative_gpa = self._calculate_gpa(completed_courses)

            return DegreeAuditResult(
                program_id=program.id,
                program_name=program.name,
                degree_type=program.degree_type,
                overall_status=overall_status,
                overall_progress_percent=round(overall_progress, 1),
                total_hours_required=total_hours_required,
                total_hours_earned=total_hours_satisfied,
                cumulative_gpa=cumulative_gpa,
                requirements=results,
                recommended_next_courses=recommended,
            )

    def what_if_analysis(
        self,
        user_id: int,
        enrollment_id: int,
        hypothetical_courses: list[dict],
    ) -> DegreeAuditResult:
        """
        Run what-if analysis with hypothetical courses added.

        Args:
            hypothetical_courses: List of dicts with course_code, grade, credit_hours
        """
        with self.session_factory() as session:
            # Get actual completed courses
            completed = self._get_completed_courses(session, user_id)

            # Add hypothetical courses
            for hypo in hypothetical_courses:
                grade = hypo.get("grade", "A")
                completed.append({
                    "course_code": hypo["course_code"].upper(),
                    "grade": grade,
                    "credit_hours": hypo.get("credit_hours", 3),
                    "is_passing": grade in PASSING_GRADES,
                    "is_hypothetical": True,
                })

            # Get enrollment and program
            enrollment = session.get(UserProgramEnrollment, enrollment_id)
            program = session.get(Program, enrollment.program_id)

            # Get requirements
            requirements = self._get_program_requirements(session, program.id)

            # Evaluate with hypothetical courses included
            results, _ = self._evaluate_requirements(requirements, completed)

            total_hours_required = program.total_hours or sum(
                r.hours_required or 0 for r in results
            )
            total_hours_satisfied = sum(r.hours_satisfied for r in results)

            overall_progress = 0
            if total_hours_required > 0:
                overall_progress = min(100, (total_hours_satisfied / total_hours_required) * 100)

            all_complete = all(r.status == SatisfactionStatus.COMPLETE for r in results)
            any_progress = any(r.status != SatisfactionStatus.INCOMPLETE for r in results)

            if all_complete:
                overall_status = SatisfactionStatus.COMPLETE
            elif any_progress:
                overall_status = SatisfactionStatus.IN_PROGRESS
            else:
                overall_status = SatisfactionStatus.INCOMPLETE

            return DegreeAuditResult(
                program_id=program.id,
                program_name=program.name,
                degree_type=program.degree_type,
                overall_status=overall_status,
                overall_progress_percent=round(overall_progress, 1),
                total_hours_required=total_hours_required,
                total_hours_earned=total_hours_satisfied,
                cumulative_gpa=self._calculate_gpa(completed),
                requirements=results,
                recommended_next_courses=[],
            )

    def _get_completed_courses(self, session: Session, user_id: int) -> list[dict]:
        """Get completed courses as list of dicts for processing."""
        courses = session.execute(
            select(UserCompletedCourse)
            .where(UserCompletedCourse.user_id == user_id)
        ).scalars().all()

        return [
            {
                "course_code": c.course_code,
                "grade": c.grade,  # Can be None for privacy
                "credit_hours": c.credit_hours,
                "is_passing": c.is_passing,  # Returns True if no grade (assumes passed)
            }
            for c in courses
        ]

    def _get_program_requirements(
        self, session: Session, program_id: int
    ) -> list[dict]:
        """Get program requirements with courses and rules."""
        reqs = session.execute(
            select(ProgramRequirement)
            .where(ProgramRequirement.program_id == program_id)
            .order_by(ProgramRequirement.display_order)
        ).scalars().all()

        result = []
        for req in reqs:
            # Get courses for this requirement
            courses = session.execute(
                select(RequirementCourse)
                .where(RequirementCourse.requirement_id == req.id)
                .order_by(RequirementCourse.display_order)
            ).scalars().all()

            # Get rules for this requirement
            rules = session.execute(
                select(RequirementRule)
                .where(RequirementRule.requirement_id == req.id)
                .order_by(RequirementRule.display_order)
            ).scalars().all()

            result.append({
                "id": req.id,
                "name": req.name,
                "category": req.category,
                "required_hours": req.required_hours,
                "min_hours": req.min_hours,
                "selection_type": req.selection_type,
                "courses_to_select": req.courses_to_select,
                "description": req.description,
                "courses": [
                    {
                        "course_code": c.course_code,
                        "credit_hours": c.credit_hours or 3,
                        "is_group": c.is_group,
                    }
                    for c in courses
                ],
                "rules": [
                    {
                        "rule_type": r.rule_type,
                        "rule_config": json.loads(r.rule_config),
                        "description": r.description,
                    }
                    for r in rules
                ],
            })

        return result

    def _evaluate_requirements(
        self,
        requirements: list[dict],
        completed: list[dict],
    ) -> tuple[list[RequirementResult], set[str]]:
        """
        Evaluate all requirements using best-fit allocation.

        Algorithm:
        1. Sort requirements: specific (course_list) first, then pools
        2. For each requirement:
           a. Find matching completed courses
           b. Apply to requirement (marking used)
        3. Return results and used course set
        """
        results = []
        used_courses: set[str] = set()

        # Create lookup of completed courses by code
        completed_map = {c["course_code"]: c for c in completed}
        completed_codes = set(completed_map.keys())

        # Sort: specific requirements first (those with explicit course lists)
        # Then pool requirements (hours_from_pool, course_level, etc.)
        specific_reqs = []
        pool_reqs = []

        for req in requirements:
            has_specific_courses = bool(req["courses"]) and req["selection_type"] == "all"
            if has_specific_courses:
                specific_reqs.append(req)
            else:
                pool_reqs.append(req)

        # Process specific requirements first
        for req in specific_reqs:
            result = self._evaluate_specific_requirement(
                req, completed_map, completed_codes, used_courses
            )
            results.append(result)

        # Process pool requirements
        for req in pool_reqs:
            result = self._evaluate_pool_requirement(
                req, completed_map, completed_codes, used_courses
            )
            results.append(result)

        return results, used_courses

    def _evaluate_specific_requirement(
        self,
        req: dict,
        completed_map: dict,
        completed_codes: set,
        used_courses: set,
    ) -> RequirementResult:
        """
        Evaluate a requirement with specific required courses.

        All listed courses must be completed (unless selection_type = "choose").
        """
        required_courses = [c["course_code"] for c in req["courses"] if not c["is_group"]]
        courses_required = len(required_courses)

        # For "choose X" requirements
        if req["selection_type"] == "choose" and req["courses_to_select"]:
            courses_required = req["courses_to_select"]

        applied = []
        hours_satisfied = 0
        remaining = []

        for course_code in required_courses:
            if course_code in completed_codes and course_code not in used_courses:
                course_info = completed_map[course_code]
                if course_info["is_passing"]:
                    applied.append(CourseApplication(
                        course_code=course_code,
                        grade=course_info["grade"],
                        credit_hours=course_info["credit_hours"],
                        is_passing=True,
                    ))
                    hours_satisfied += course_info["credit_hours"]
                    used_courses.add(course_code)
            else:
                remaining.append(course_code)

        courses_satisfied = len(applied)

        # Determine status
        if courses_satisfied >= courses_required:
            status = SatisfactionStatus.COMPLETE
        elif courses_satisfied > 0:
            status = SatisfactionStatus.IN_PROGRESS
        else:
            status = SatisfactionStatus.INCOMPLETE

        return RequirementResult(
            requirement_id=req["id"],
            requirement_name=req["name"],
            category=req["category"],
            status=status,
            hours_required=req["required_hours"] or sum(c["credit_hours"] for c in req["courses"]),
            hours_satisfied=hours_satisfied,
            courses_required=courses_required,
            courses_satisfied=courses_satisfied,
            courses_applied=applied,
            remaining_courses=remaining[:5],  # Limit remaining list
            description=req["description"] or f"Complete {courses_required} courses",
        )

    def _evaluate_pool_requirement(
        self,
        req: dict,
        completed_map: dict,
        completed_codes: set,
        used_courses: set,
    ) -> RequirementResult:
        """
        Evaluate a pool requirement (hours from subject/level/etc.).

        Uses rules to determine which courses qualify.
        """
        # Default: use any listed courses or rules
        hours_required = req["required_hours"] or req["min_hours"] or 0
        hours_satisfied = 0
        applied = []
        gpa_required = None
        gpa_achieved = None

        # Process rules
        for rule in req.get("rules", []):
            rule_type = rule["rule_type"]
            config = rule["rule_config"]

            if rule_type == "hours_from_pool":
                # Find courses matching pool criteria
                hours_needed = config.get("hours", hours_required)
                subjects = config.get("subjects", [])
                min_level = config.get("min_level", 0)

                for code in completed_codes - used_courses:
                    if hours_satisfied >= hours_needed:
                        break

                    course = completed_map[code]
                    if not course["is_passing"]:
                        continue

                    # Check subject match
                    subject = code.split()[0] if " " in code else ""
                    if subjects and subject not in subjects:
                        continue

                    # Check level match
                    try:
                        level = int(code.split()[-1][0]) * 1000
                        if level < min_level:
                            continue
                    except (ValueError, IndexError):
                        continue

                    # Apply course
                    applied.append(CourseApplication(
                        course_code=code,
                        grade=course["grade"],
                        credit_hours=course["credit_hours"],
                        is_passing=True,
                    ))
                    hours_satisfied += course["credit_hours"]
                    used_courses.add(code)

                hours_required = hours_needed

            elif rule_type == "course_level":
                # Upper division hours requirement
                hours_needed = config.get("hours", hours_required)
                min_level = config.get("min_level", 3000)

                for code in completed_codes - used_courses:
                    if hours_satisfied >= hours_needed:
                        break

                    course = completed_map[code]
                    if not course["is_passing"]:
                        continue

                    try:
                        level = int(code.split()[-1][0]) * 1000
                        if level < min_level:
                            continue
                    except (ValueError, IndexError):
                        continue

                    applied.append(CourseApplication(
                        course_code=code,
                        grade=course["grade"],
                        credit_hours=course["credit_hours"],
                        is_passing=True,
                    ))
                    hours_satisfied += course["credit_hours"]
                    used_courses.add(code)

                hours_required = hours_needed

            elif rule_type == "gpa_minimum":
                # GPA requirement
                gpa_required = config.get("gpa", 2.0)
                scope = config.get("scope", "all")

                # Calculate GPA for relevant courses
                relevant_courses = []
                for code in completed_codes:
                    course = completed_map[code]
                    if scope == "major" and req["category"] != "major":
                        continue
                    relevant_courses.append(course)

                gpa_achieved = self._calculate_gpa(relevant_courses)

            elif rule_type == "course_list":
                # Specific courses from a list
                valid_courses = config.get("courses", [])
                select_count = config.get("select")

                for code in valid_courses:
                    if code in completed_codes and code not in used_courses:
                        course = completed_map[code]
                        if course["is_passing"]:
                            applied.append(CourseApplication(
                                course_code=code,
                                grade=course["grade"],
                                credit_hours=course["credit_hours"],
                                is_passing=True,
                            ))
                            hours_satisfied += course["credit_hours"]
                            used_courses.add(code)

                            if select_count and len(applied) >= select_count:
                                break

        # If no rules, try to use listed courses
        if not req.get("rules") and req.get("courses"):
            for course_info in req["courses"]:
                code = course_info["course_code"]
                if code in completed_codes and code not in used_courses:
                    course = completed_map[code]
                    if course["is_passing"]:
                        applied.append(CourseApplication(
                            course_code=code,
                            grade=course["grade"],
                            credit_hours=course["credit_hours"],
                            is_passing=True,
                        ))
                        hours_satisfied += course["credit_hours"]
                        used_courses.add(code)

        # Determine status
        if gpa_required:
            # GPA-based requirement
            if gpa_achieved and gpa_achieved >= gpa_required:
                status = SatisfactionStatus.COMPLETE
            else:
                status = SatisfactionStatus.INCOMPLETE
        elif hours_required > 0:
            if hours_satisfied >= hours_required:
                status = SatisfactionStatus.COMPLETE
            elif hours_satisfied > 0:
                status = SatisfactionStatus.IN_PROGRESS
            else:
                status = SatisfactionStatus.INCOMPLETE
        else:
            status = SatisfactionStatus.COMPLETE if applied else SatisfactionStatus.INCOMPLETE

        return RequirementResult(
            requirement_id=req["id"],
            requirement_name=req["name"],
            category=req["category"],
            status=status,
            hours_required=hours_required or None,
            hours_satisfied=hours_satisfied,
            courses_required=None,
            courses_satisfied=len(applied),
            gpa_required=gpa_required,
            gpa_achieved=gpa_achieved,
            courses_applied=applied,
            remaining_courses=[],
            description=req["description"] or f"Complete {hours_required} hours",
        )

    def _calculate_gpa(self, courses: list[dict]) -> Optional[float]:
        """Calculate GPA from list of course dicts. Only includes courses with grades."""
        total_points = 0.0
        total_hours = 0

        for course in courses:
            grade = course.get("grade")
            if not grade:
                continue  # Skip courses without grades (privacy)
            grade = grade.upper()
            hours = course.get("credit_hours", 3)

            if grade in GRADE_POINTS:
                total_points += GRADE_POINTS[grade] * hours
                total_hours += hours

        if total_hours > 0:
            return round(total_points / total_hours, 3)
        return None

    def _get_recommended_courses(
        self,
        results: list[RequirementResult],
        completed: list[dict],
    ) -> list[str]:
        """Get recommended next courses based on incomplete requirements."""
        completed_codes = {c["course_code"] for c in completed}
        recommendations = []

        for result in results:
            if result.status != SatisfactionStatus.COMPLETE:
                for course in result.remaining_courses:
                    if course not in completed_codes and course not in recommendations:
                        recommendations.append(course)
                        if len(recommendations) >= 10:
                            return recommendations

        return recommendations


def create_rules_engine() -> RulesEngine:
    """Create a RulesEngine instance with default configuration."""
    return RulesEngine()
