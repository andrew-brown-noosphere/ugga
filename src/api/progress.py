"""
Student Progress API endpoints.

Handles:
- Completed courses CRUD
- Program enrollments
- Transcript summary
- Degree audits
- What-if analysis
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Query

from src.models.database import User, PlannedSection, get_session_factory
from src.api.schemas import (
    # Completed courses
    CompletedCourseCreate,
    CompletedCourseBulkCreate,
    CompletedCourseUpdate,
    CompletedCourseResponse,
    CompletedCoursesResponse,
    # Planned sections
    PlannedSectionCreate,
    PlannedSectionResponse,
    PlannedSectionsResponse,
    # Transcript
    TranscriptSummaryResponse,
    # Enrollments
    ProgramEnrollmentCreate,
    ProgramEnrollmentResponse,
    ProgramEnrollmentsResponse,
    # Audit
    DegreeAuditResponse,
    RequirementResultResponse,
    CourseApplicationResponse,
    WhatIfRequest,
    QuickProgressResponse,
    # Graduation path
    GraduationPathRequest,
    GraduationPathResponse,
    SemesterPlanResponse,
    CourseOptionResponse,
    WhatIfScenariosRequest,
    WhatIfScenariosResponse,
    WhatIfScenarioResult,
)
from src.api.auth import get_current_user
from src.services.progress_service import ProgressService, create_progress_service
from src.services.audit_service import AuditService, create_audit_service
from src.services.rules_engine import SatisfactionStatus
from src.services.graduation_optimizer import (
    GraduationOptimizer, OptimizationMode, create_graduation_optimizer
)

router = APIRouter(prefix="/progress", tags=["Progress"])

# Service instances
_progress_service: Optional[ProgressService] = None
_audit_service: Optional[AuditService] = None
_graduation_optimizer: Optional[GraduationOptimizer] = None


def get_progress_service() -> ProgressService:
    """Dependency to get ProgressService instance."""
    global _progress_service
    if _progress_service is None:
        _progress_service = create_progress_service()
    return _progress_service


def get_audit_service() -> AuditService:
    """Dependency to get AuditService instance."""
    global _audit_service
    if _audit_service is None:
        _audit_service = create_audit_service()
    return _audit_service


def get_graduation_optimizer() -> GraduationOptimizer:
    """Dependency to get GraduationOptimizer instance."""
    global _graduation_optimizer
    if _graduation_optimizer is None:
        _graduation_optimizer = create_graduation_optimizer()
    return _graduation_optimizer


# =============================================================================
# Completed Courses Endpoints
# =============================================================================

@router.get("/courses", response_model=CompletedCoursesResponse)
async def get_completed_courses(
    semester: Optional[str] = Query(None, description="Filter by semester"),
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
):
    """Get user's completed courses."""
    courses = service.get_completed_courses(user.id, semester)
    return CompletedCoursesResponse(
        courses=[
            CompletedCourseResponse(
                id=c.id,
                course_code=c.course_code,
                grade=c.grade,
                credit_hours=c.credit_hours,
                quality_points=c.quality_points,
                semester=c.semester,
                year=c.year,
                source=c.source,
                verified=c.verified,
                is_passing=c.is_passing,
                grade_points=c.grade_points,
                created_at=c.created_at,
            )
            for c in courses
        ],
        total=len(courses),
    )


@router.post("/courses", response_model=CompletedCourseResponse)
async def add_completed_course(
    course: CompletedCourseCreate,
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Add a completed course for the current user."""
    try:
        completed = service.add_completed_course(
            user_id=user.id,
            course_code=course.course_code,
            grade=course.grade,
            credit_hours=course.credit_hours,
            semester=course.semester,
            year=course.year,
        )

        # Invalidate audit cache
        audit_service.invalidate_cache(user.id)

        return CompletedCourseResponse(
            id=completed.id,
            course_code=completed.course_code,
            grade=completed.grade,
            credit_hours=completed.credit_hours,
            quality_points=completed.quality_points,
            semester=completed.semester,
            year=completed.year,
            source=completed.source,
            verified=completed.verified,
            is_passing=completed.is_passing,
            grade_points=completed.grade_points,
            created_at=completed.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/courses/bulk", response_model=CompletedCoursesResponse)
async def add_completed_courses_bulk(
    data: CompletedCourseBulkCreate,
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Add multiple completed courses at once."""
    courses_data = [
        {
            "course_code": c.course_code,
            "grade": c.grade,
            "credit_hours": c.credit_hours,
            "semester": c.semester,
            "year": c.year,
        }
        for c in data.courses
    ]

    completed_list = service.add_completed_courses_bulk(user.id, courses_data)

    # Invalidate audit cache
    audit_service.invalidate_cache(user.id)

    return CompletedCoursesResponse(
        courses=[
            CompletedCourseResponse(
                id=c.id,
                course_code=c.course_code,
                grade=c.grade,
                credit_hours=c.credit_hours,
                quality_points=c.quality_points,
                semester=c.semester,
                year=c.year,
                source=c.source,
                verified=c.verified,
                is_passing=c.is_passing,
                grade_points=c.grade_points,
                created_at=c.created_at,
            )
            for c in completed_list
        ],
        total=len(completed_list),
    )


@router.put("/courses/{course_id}", response_model=CompletedCourseResponse)
async def update_completed_course(
    course_id: int,
    update: CompletedCourseUpdate,
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Update a completed course."""
    try:
        # Verify ownership (will fail if not found or not user's)
        courses = service.get_completed_courses(user.id)
        if not any(c.id == course_id for c in courses):
            raise HTTPException(status_code=404, detail="Course not found")

        completed = service.update_completed_course(
            course_id=course_id,
            grade=update.grade,
            credit_hours=update.credit_hours,
            semester=update.semester,
            year=update.year,
        )

        # Invalidate audit cache
        audit_service.invalidate_cache(user.id)

        return CompletedCourseResponse(
            id=completed.id,
            course_code=completed.course_code,
            grade=completed.grade,
            credit_hours=completed.credit_hours,
            quality_points=completed.quality_points,
            semester=completed.semester,
            year=completed.year,
            source=completed.source,
            verified=completed.verified,
            is_passing=completed.is_passing,
            grade_points=completed.grade_points,
            created_at=completed.created_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/courses/{course_id}")
async def delete_completed_course(
    course_id: int,
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
    audit_service: AuditService = Depends(get_audit_service),
):
    """Delete a completed course."""
    # Verify ownership
    courses = service.get_completed_courses(user.id)
    if not any(c.id == course_id for c in courses):
        raise HTTPException(status_code=404, detail="Course not found")

    success = service.delete_completed_course(course_id)
    if not success:
        raise HTTPException(status_code=404, detail="Course not found")

    # Invalidate audit cache
    audit_service.invalidate_cache(user.id)

    return {"status": "deleted"}


# =============================================================================
# Transcript Summary Endpoints
# =============================================================================

@router.get("/summary", response_model=TranscriptSummaryResponse)
async def get_transcript_summary(
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
):
    """Get user's transcript summary (GPA, hours, etc.)."""
    summary = service.get_transcript_summary(user.id)
    if not summary:
        raise HTTPException(status_code=404, detail="No transcript data found")

    return TranscriptSummaryResponse.model_validate(summary)


# =============================================================================
# Program Enrollment Endpoints
# =============================================================================

@router.get("/enrollments", response_model=ProgramEnrollmentsResponse)
async def get_program_enrollments(
    active_only: bool = Query(True, description="Only return active enrollments"),
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
):
    """Get user's program enrollments."""
    enrollments = service.get_program_enrollments(user.id, active_only)

    session_factory = get_session_factory()
    with session_factory() as session:
        responses = []
        for e in enrollments:
            from src.models.database import Program
            program = session.get(Program, e.program_id)
            responses.append(ProgramEnrollmentResponse(
                id=e.id,
                program_id=e.program_id,
                program_name=program.name if program else None,
                enrollment_type=e.enrollment_type,
                is_primary=e.is_primary,
                status=e.status,
                catalog_year=e.catalog_year,
                expected_graduation=e.expected_graduation,
                enrollment_date=e.enrollment_date,
            ))

    return ProgramEnrollmentsResponse(enrollments=responses)


@router.post("/enrollments", response_model=ProgramEnrollmentResponse)
async def enroll_in_program(
    enrollment: ProgramEnrollmentCreate,
    user: User = Depends(get_current_user),
    service: ProgressService = Depends(get_progress_service),
):
    """Enroll in a degree program."""
    try:
        enrolled = service.enroll_in_program(
            user_id=user.id,
            program_id=enrollment.program_id,
            enrollment_type=enrollment.enrollment_type,
            is_primary=enrollment.is_primary,
            catalog_year=enrollment.catalog_year,
        )

        session_factory = get_session_factory()
        with session_factory() as session:
            from src.models.database import Program
            program = session.get(Program, enrolled.program_id)
            return ProgramEnrollmentResponse(
                id=enrolled.id,
                program_id=enrolled.program_id,
                program_name=program.name if program else None,
                enrollment_type=enrolled.enrollment_type,
                is_primary=enrolled.is_primary,
                status=enrolled.status,
                catalog_year=enrolled.catalog_year,
                expected_graduation=enrolled.expected_graduation,
                enrollment_date=enrolled.enrollment_date,
            )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# =============================================================================
# Degree Audit Endpoints
# =============================================================================

@router.get("/audit", response_model=DegreeAuditResponse)
async def run_degree_audit(
    enrollment_id: Optional[int] = Query(None, description="Specific enrollment to audit"),
    user: User = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Run a full degree audit for the user's primary (or specified) enrollment."""
    try:
        result = service.run_audit(user.id, enrollment_id)

        return DegreeAuditResponse(
            program_id=result.program_id,
            program_name=result.program_name,
            degree_type=result.degree_type,
            overall_status=result.overall_status.value,
            overall_progress_percent=result.overall_progress_percent,
            total_hours_required=result.total_hours_required,
            total_hours_earned=result.total_hours_earned,
            cumulative_gpa=result.cumulative_gpa,
            requirements=[
                RequirementResultResponse(
                    requirement_id=r.requirement_id,
                    requirement_name=r.requirement_name,
                    category=r.category,
                    status=r.status.value,
                    hours_required=r.hours_required,
                    hours_satisfied=r.hours_satisfied,
                    courses_required=r.courses_required,
                    courses_satisfied=r.courses_satisfied,
                    gpa_required=r.gpa_required,
                    gpa_achieved=r.gpa_achieved,
                    progress_percent=r.progress_percent,
                    courses_applied=[
                        CourseApplicationResponse(
                            course_code=c.course_code,
                            grade=c.grade,
                            credit_hours=c.credit_hours,
                            is_passing=c.is_passing,
                        )
                        for c in r.courses_applied
                    ],
                    remaining_courses=r.remaining_courses,
                    description=r.description,
                )
                for r in result.requirements
            ],
            recommended_next_courses=result.recommended_next_courses,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/audit/what-if", response_model=DegreeAuditResponse)
async def what_if_analysis(
    data: WhatIfRequest,
    enrollment_id: Optional[int] = Query(None, description="Specific enrollment to audit"),
    user: User = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
    progress_service: ProgressService = Depends(get_progress_service),
):
    """
    Run what-if analysis with hypothetical courses.

    Shows what degree progress would look like if the user completed
    the specified hypothetical courses.
    """
    try:
        # Get enrollment
        if enrollment_id is None:
            enrollment = progress_service.get_primary_enrollment(user.id)
            if not enrollment:
                raise ValueError("No primary program enrollment found")
            enrollment_id = enrollment.id

        # Convert to dicts
        hypothetical = [
            {
                "course_code": c.course_code,
                "grade": c.grade,
                "credit_hours": c.credit_hours,
            }
            for c in data.hypothetical_courses
        ]

        result = service.what_if_analysis(user.id, enrollment_id, hypothetical)

        return DegreeAuditResponse(
            program_id=result.program_id,
            program_name=result.program_name,
            degree_type=result.degree_type,
            overall_status=result.overall_status.value,
            overall_progress_percent=result.overall_progress_percent,
            total_hours_required=result.total_hours_required,
            total_hours_earned=result.total_hours_earned,
            cumulative_gpa=result.cumulative_gpa,
            requirements=[
                RequirementResultResponse(
                    requirement_id=r.requirement_id,
                    requirement_name=r.requirement_name,
                    category=r.category,
                    status=r.status.value,
                    hours_required=r.hours_required,
                    hours_satisfied=r.hours_satisfied,
                    courses_required=r.courses_required,
                    courses_satisfied=r.courses_satisfied,
                    gpa_required=r.gpa_required,
                    gpa_achieved=r.gpa_achieved,
                    progress_percent=r.progress_percent,
                    courses_applied=[
                        CourseApplicationResponse(
                            course_code=c.course_code,
                            grade=c.grade,
                            credit_hours=c.credit_hours,
                            is_passing=c.is_passing,
                        )
                        for c in r.courses_applied
                    ],
                    remaining_courses=r.remaining_courses,
                    description=r.description,
                )
                for r in result.requirements
            ],
            recommended_next_courses=result.recommended_next_courses,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/quick", response_model=QuickProgressResponse)
async def get_quick_progress(
    user: User = Depends(get_current_user),
    service: AuditService = Depends(get_audit_service),
):
    """Get quick progress summary without full audit."""
    result = service.get_quick_progress(user.id)
    return QuickProgressResponse(**result)


# =============================================================================
# Planned Sections (Semester Schedule) Endpoints
# =============================================================================

@router.get("/planned", response_model=PlannedSectionsResponse)
async def get_planned_sections(
    semester: Optional[str] = Query(None, description="Filter by semester (e.g., Spring 2026)"),
    user: User = Depends(get_current_user),
):
    """Get user's planned sections for a semester."""
    try:
        session_factory = get_session_factory()
        with session_factory() as session:
            query = session.query(PlannedSection).filter(
                PlannedSection.user_id == user.id
            )

            if semester:
                query = query.filter(PlannedSection.semester == semester)

            query = query.order_by(PlannedSection.created_at.desc())
            sections = query.all()

            return PlannedSectionsResponse(
                sections=[PlannedSectionResponse.model_validate(s) for s in sections],
                total=len(sections),
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/planned", response_model=PlannedSectionResponse)
async def add_planned_section(
    data: PlannedSectionCreate,
    user: User = Depends(get_current_user),
):
    """Add a section to the user's plan."""
    from sqlalchemy.exc import IntegrityError

    session_factory = get_session_factory()
    with session_factory() as session:
        # Check if already added
        existing = session.query(PlannedSection).filter(
            PlannedSection.user_id == user.id,
            PlannedSection.crn == data.crn,
            PlannedSection.semester == data.semester,
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Section already in your plan")

        section = PlannedSection(
            user_id=user.id,
            crn=data.crn,
            course_code=data.course_code,
            course_title=data.course_title,
            instructor=data.instructor,
            days=data.days,
            start_time=data.start_time,
            end_time=data.end_time,
            building=data.building,
            room=data.room,
            semester=data.semester,
        )

        session.add(section)
        try:
            session.commit()
            session.refresh(section)
            return PlannedSectionResponse.model_validate(section)
        except IntegrityError:
            session.rollback()
            raise HTTPException(status_code=400, detail="Section already in your plan")


@router.delete("/planned/{section_id}")
async def remove_planned_section(
    section_id: int,
    user: User = Depends(get_current_user),
):
    """Remove a section from the user's plan."""
    session_factory = get_session_factory()
    with session_factory() as session:
        section = session.query(PlannedSection).filter(
            PlannedSection.id == section_id,
            PlannedSection.user_id == user.id,
        ).first()

        if not section:
            raise HTTPException(status_code=404, detail="Section not found in your plan")

        session.delete(section)
        session.commit()

        return {"status": "removed"}


# =============================================================================
# Graduation Path Optimizer Endpoints
# =============================================================================

@router.post("/graduation-path", response_model=GraduationPathResponse)
async def generate_graduation_path(
    request: GraduationPathRequest,
    user: User = Depends(get_current_user),
    optimizer: GraduationOptimizer = Depends(get_graduation_optimizer),
):
    """
    Generate an optimized graduation path.

    Modes:
    - graduate_asap: Minimize semesters to graduation (max credit hours)
    - party_mode: Easy classes, good instructors, optimal social schedule
    - balanced: Balance between speed and difficulty
    - interest_based: Align electives with student interests
    """
    try:
        # Convert string mode to enum
        mode = OptimizationMode(request.mode)

        path = optimizer.generate_path(
            user_id=user.id,
            mode=mode,
            hours_per_semester=request.hours_per_semester,
            start_semester=request.start_semester,
            interests=request.interests,
        )

        return GraduationPathResponse(
            program_name=path.program_name,
            degree_type=path.degree_type,
            optimization_mode=path.optimization_mode.value,
            current_hours=path.current_hours,
            hours_remaining=path.hours_remaining,
            semesters=[
                SemesterPlanResponse(
                    semester=sem.semester,
                    courses=[
                        CourseOptionResponse(
                            course_code=c.course_code,
                            title=c.title,
                            credit_hours=c.credit_hours,
                            requirement_name=c.requirement_name,
                            requirement_category=c.requirement_category,
                            sections_available=c.sections_available,
                            seats_available=c.seats_available,
                            avg_instructor_rating=c.avg_instructor_rating,
                            avg_difficulty=c.avg_difficulty,
                            easiest_section_instructor=c.easiest_section_instructor,
                            easiest_section_crn=c.easiest_section_crn,
                            prerequisites=c.prerequisites,
                            prereqs_satisfied=c.prereqs_satisfied,
                            priority_score=c.priority_score,
                        )
                        for c in sem.courses
                    ],
                    total_hours=sem.total_hours,
                    avg_difficulty=sem.avg_difficulty,
                    total_walking_minutes=sem.total_walking_minutes,
                    notes=sem.notes,
                )
                for sem in path.semesters
            ],
            estimated_graduation=path.estimated_graduation,
            total_semesters_remaining=path.total_semesters_remaining,
            warnings=path.warnings,
            generated_at=path.generated_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/graduation-path/scenarios", response_model=WhatIfScenariosResponse)
async def compare_graduation_scenarios(
    request: WhatIfScenariosRequest,
    user: User = Depends(get_current_user),
    optimizer: GraduationOptimizer = Depends(get_graduation_optimizer),
):
    """
    Compare multiple what-if scenarios for graduation planning.

    Example scenarios:
    - "Take summer classes" with ["CSCI 1302", "MATH 2250"]
    - "Light fall semester" with ["ENGL 1101", "HIST 2111"]
    """
    try:
        scenarios_data = [
            {"name": s.name, "courses": s.courses}
            for s in request.scenarios
        ]

        results = optimizer.get_what_if_scenarios(user.id, scenarios_data)

        return WhatIfScenariosResponse(
            scenarios=[
                WhatIfScenarioResult(
                    name=r["name"],
                    courses_added=r["courses_added"],
                    new_progress_percent=r["new_progress_percent"],
                    hours_after=r["hours_after"],
                    hours_remaining=r["hours_remaining"],
                    estimated_semesters_remaining=r["estimated_semesters_remaining"],
                )
                for r in results
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/graduation-path/party-mode", response_model=SemesterPlanResponse)
async def get_party_mode_schedule(
    semester: str = Query(..., description="Target semester (e.g., Fall 2026)"),
    target_hours: int = Query(12, ge=12, le=15, description="Target credit hours (12-15 for party mode)"),
    user: User = Depends(get_current_user),
    optimizer: GraduationOptimizer = Depends(get_graduation_optimizer),
):
    """
    Generate a party mode schedule for a specific semester.

    Optimizes for:
    - Low difficulty classes (easy professors)
    - Good instructor ratings
    - No early morning classes (optional)
    - Minimal walking between buildings
    """
    try:
        plan = optimizer.generate_party_mode_schedule(
            user_id=user.id,
            semester=semester,
            target_hours=target_hours,
        )

        return SemesterPlanResponse(
            semester=plan.semester,
            courses=[
                CourseOptionResponse(
                    course_code=c.course_code,
                    title=c.title,
                    credit_hours=c.credit_hours,
                    requirement_name=c.requirement_name,
                    requirement_category=c.requirement_category,
                    sections_available=c.sections_available,
                    seats_available=c.seats_available,
                    avg_instructor_rating=c.avg_instructor_rating,
                    avg_difficulty=c.avg_difficulty,
                    easiest_section_instructor=c.easiest_section_instructor,
                    easiest_section_crn=c.easiest_section_crn,
                    prerequisites=c.prerequisites,
                    prereqs_satisfied=c.prereqs_satisfied,
                    priority_score=c.priority_score,
                )
                for c in plan.courses
            ],
            total_hours=plan.total_hours,
            avg_difficulty=plan.avg_difficulty,
            total_walking_minutes=plan.total_walking_minutes,
            notes=plan.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
