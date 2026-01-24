"""
Degree Audit Service.

Orchestrates degree audits by:
- Running the rules engine
- Caching results in user_requirement_satisfactions
- Providing quick access to cached audit results

Caches are invalidated when courses are added/removed.
"""
import json
from datetime import datetime
from typing import Optional
from sqlalchemy import select, delete, and_
from sqlalchemy.orm import Session

from src.models.database import (
    User, UserCompletedCourse, UserProgramEnrollment,
    UserRequirementSatisfaction, CourseRequirementApplication,
    Program, ProgramRequirement,
    get_engine, get_session_factory
)
from src.services.rules_engine import (
    RulesEngine, DegreeAuditResult, RequirementResult, SatisfactionStatus
)
from src.services.progress_service import ProgressService


class AuditService:
    """Service for running and caching degree audits."""

    def __init__(self, session_factory=None):
        if session_factory is None:
            engine = get_engine()
            session_factory = get_session_factory(engine)
        self.session_factory = session_factory
        self.rules_engine = RulesEngine(session_factory)
        self.progress_service = ProgressService(session_factory)

    def run_audit(
        self,
        user_id: int,
        enrollment_id: Optional[int] = None,
        force_refresh: bool = False,
    ) -> DegreeAuditResult:
        """
        Run a degree audit for a user.

        Args:
            user_id: The user ID
            enrollment_id: Specific enrollment to audit, or None for primary
            force_refresh: If True, bypass cache and run fresh audit

        Returns:
            DegreeAuditResult with all requirement evaluations
        """
        with self.session_factory() as session:
            # Get enrollment
            if enrollment_id is None:
                enrollment = self.progress_service.get_primary_enrollment(user_id)
                if not enrollment:
                    raise ValueError("User has no primary program enrollment")
                enrollment_id = enrollment.id
            else:
                enrollment = session.get(UserProgramEnrollment, enrollment_id)
                if not enrollment or enrollment.user_id != user_id:
                    raise ValueError("Invalid enrollment")

            # Run fresh audit via rules engine
            result = self.rules_engine.run_audit(user_id, enrollment_id)

            # Cache results
            self._cache_audit_results(session, user_id, enrollment_id, result)
            session.commit()

            return result

    def get_cached_audit(
        self,
        user_id: int,
        enrollment_id: int,
    ) -> Optional[DegreeAuditResult]:
        """
        Get cached audit results if available.

        Returns None if no cached results exist.
        """
        with self.session_factory() as session:
            # Get cached satisfactions
            satisfactions = session.execute(
                select(UserRequirementSatisfaction)
                .where(and_(
                    UserRequirementSatisfaction.user_id == user_id,
                    UserRequirementSatisfaction.enrollment_id == enrollment_id,
                ))
            ).scalars().all()

            if not satisfactions:
                return None

            # Get enrollment and program info
            enrollment = session.get(UserProgramEnrollment, enrollment_id)
            if not enrollment:
                return None

            program = session.get(Program, enrollment.program_id)
            if not program:
                return None

            # Reconstruct result from cache
            requirements = []
            for sat in satisfactions:
                req = session.get(ProgramRequirement, sat.requirement_id)
                if not req:
                    continue

                # Parse courses applied
                courses_applied = []
                if sat.courses_applied_json:
                    try:
                        courses_data = json.loads(sat.courses_applied_json)
                        for c in courses_data:
                            courses_applied.append({
                                "course_code": c.get("course_code", ""),
                                "grade": c.get("grade", ""),
                                "credit_hours": c.get("credit_hours", 3),
                                "is_passing": c.get("is_passing", True),
                            })
                    except json.JSONDecodeError:
                        pass

                requirements.append(RequirementResult(
                    requirement_id=sat.requirement_id,
                    requirement_name=req.name,
                    category=req.category,
                    status=SatisfactionStatus(sat.status),
                    hours_required=sat.hours_required,
                    hours_satisfied=sat.hours_satisfied,
                    courses_required=sat.courses_required,
                    courses_satisfied=sat.courses_satisfied,
                    gpa_required=sat.gpa_required,
                    gpa_achieved=sat.gpa_achieved,
                    courses_applied=[],  # Simplified for cache
                    remaining_courses=[],
                    description=req.description or "",
                ))

            if not requirements:
                return None

            # Calculate overall metrics
            total_hours_required = program.total_hours or sum(
                r.hours_required or 0 for r in requirements
            )
            total_hours_earned = sum(r.hours_satisfied for r in requirements)
            overall_progress = 0
            if total_hours_required > 0:
                overall_progress = min(100, (total_hours_earned / total_hours_required) * 100)

            all_complete = all(r.status == SatisfactionStatus.COMPLETE for r in requirements)
            any_progress = any(r.status != SatisfactionStatus.INCOMPLETE for r in requirements)

            if all_complete:
                overall_status = SatisfactionStatus.COMPLETE
            elif any_progress:
                overall_status = SatisfactionStatus.IN_PROGRESS
            else:
                overall_status = SatisfactionStatus.INCOMPLETE

            # Get transcript summary for GPA
            summary = self.progress_service.get_transcript_summary(user_id)
            cumulative_gpa = summary.cumulative_gpa if summary else None

            return DegreeAuditResult(
                program_id=program.id,
                program_name=program.name,
                degree_type=program.degree_type,
                overall_status=overall_status,
                overall_progress_percent=round(overall_progress, 1),
                total_hours_required=total_hours_required,
                total_hours_earned=total_hours_earned,
                cumulative_gpa=cumulative_gpa,
                requirements=requirements,
                recommended_next_courses=[],
            )

    def invalidate_cache(self, user_id: int, enrollment_id: Optional[int] = None) -> None:
        """
        Invalidate cached audit results.

        Called when courses are added/removed/updated.
        """
        with self.session_factory() as session:
            query = delete(UserRequirementSatisfaction).where(
                UserRequirementSatisfaction.user_id == user_id
            )
            if enrollment_id:
                query = query.where(
                    UserRequirementSatisfaction.enrollment_id == enrollment_id
                )
            session.execute(query)
            session.commit()

    def what_if_analysis(
        self,
        user_id: int,
        enrollment_id: int,
        hypothetical_courses: list[dict],
    ) -> DegreeAuditResult:
        """
        Run what-if analysis with hypothetical courses.

        Does not cache results.
        """
        return self.rules_engine.what_if_analysis(
            user_id, enrollment_id, hypothetical_courses
        )

    def get_quick_progress(self, user_id: int) -> dict:
        """
        Get quick progress summary without full audit.

        Returns basic metrics from transcript summary.
        """
        with self.session_factory() as session:
            # Get transcript summary
            summary = self.progress_service.get_transcript_summary(user_id)

            # Get primary enrollment
            enrollment = self.progress_service.get_primary_enrollment(user_id)

            if not summary or not enrollment:
                return {
                    "has_progress": False,
                    "total_hours_earned": 0,
                    "cumulative_gpa": None,
                    "program_name": None,
                    "progress_percent": 0,
                }

            # Get program for total hours
            program = session.get(Program, enrollment.program_id)
            total_required = program.total_hours if program else 120

            progress_percent = 0
            if total_required > 0:
                progress_percent = min(100, (summary.total_hours_earned / total_required) * 100)

            return {
                "has_progress": True,
                "total_hours_earned": summary.total_hours_earned,
                "total_hours_required": total_required,
                "cumulative_gpa": summary.cumulative_gpa,
                "upper_division_hours": summary.upper_division_hours,
                "program_name": program.name if program else None,
                "progress_percent": round(progress_percent, 1),
            }

    def _cache_audit_results(
        self,
        session: Session,
        user_id: int,
        enrollment_id: int,
        result: DegreeAuditResult,
    ) -> None:
        """Cache audit results to database."""
        # Clear existing cache
        session.execute(
            delete(UserRequirementSatisfaction)
            .where(and_(
                UserRequirementSatisfaction.user_id == user_id,
                UserRequirementSatisfaction.enrollment_id == enrollment_id,
            ))
        )

        # Insert new satisfaction records
        for req_result in result.requirements:
            # Serialize courses applied
            courses_json = json.dumps([
                {
                    "course_code": c.course_code,
                    "grade": c.grade,
                    "credit_hours": c.credit_hours,
                    "is_passing": c.is_passing,
                }
                for c in req_result.courses_applied
            ]) if req_result.courses_applied else None

            satisfaction = UserRequirementSatisfaction(
                user_id=user_id,
                enrollment_id=enrollment_id,
                requirement_id=req_result.requirement_id,
                status=req_result.status.value,
                hours_required=req_result.hours_required,
                hours_satisfied=req_result.hours_satisfied,
                courses_required=req_result.courses_required,
                courses_satisfied=req_result.courses_satisfied,
                gpa_required=req_result.gpa_required,
                gpa_achieved=req_result.gpa_achieved,
                courses_applied_json=courses_json,
                calculated_at=datetime.utcnow(),
            )
            session.add(satisfaction)


def create_audit_service() -> AuditService:
    """Create an AuditService instance with default configuration."""
    return AuditService()
