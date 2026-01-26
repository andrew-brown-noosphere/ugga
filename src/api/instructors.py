"""
Instructor profile and claim API endpoints.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from src.api.auth import get_current_user, get_optional_user
from src.api.schemas import (
    ProfessorResponse,
    ProfessorListResponse,
    ProfessorCourseResponse,
    ClaimProfileRequest,
    ClaimProfileResponse,
    ProfessorProfileUpdate,
    SyllabusResponse,
)
from src.models.database import (
    Professor,
    ProfessorCourse,
    User,
    BulletinCourse,
    get_session_factory,
)

router = APIRouter(prefix="/instructors", tags=["Instructors"])


def get_db():
    """Get database session."""
    session_factory = get_session_factory()
    with session_factory() as session:
        yield session


@router.get("", response_model=list[ProfessorListResponse])
async def list_instructors(
    search: Optional[str] = None,
    department: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """List instructors with optional search/filter."""
    query = select(Professor)

    if search:
        query = query.where(
            Professor.name.ilike(f"%{search}%")
        )

    if department:
        query = query.join(Professor.department).where(
            func.lower(Professor.department.has(name=department))
        )

    query = query.order_by(Professor.last_name, Professor.first_name)
    query = query.offset(offset).limit(limit)

    professors = db.execute(query).scalars().all()

    return [
        ProfessorListResponse(
            id=p.id,
            name=p.name,
            title=p.title,
            email=p.email,
            department_name=p.department.name if p.department else None,
            photo_url=p.photo_url,
            rmp_rating=p.instructor.rmp_rating if p.instructor else None,
        )
        for p in professors
    ]


@router.get("/{instructor_id}", response_model=ProfessorResponse)
async def get_instructor(
    instructor_id: int,
    db: Session = Depends(get_db),
):
    """Get instructor profile by ID."""
    professor = db.execute(
        select(Professor)
        .options(joinedload(Professor.department), joinedload(Professor.instructor))
        .where(Professor.id == instructor_id)
    ).scalar_one_or_none()

    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    return ProfessorResponse(
        id=professor.id,
        name=professor.name,
        first_name=professor.first_name,
        last_name=professor.last_name,
        title=professor.title,
        email=professor.email,
        phone=professor.phone,
        office_location=professor.office_location,
        office_hours=professor.office_hours,
        photo_url=professor.photo_url,
        profile_url=professor.profile_url,
        bio=professor.bio,
        research_areas=professor.research_areas,
        education=professor.education,
        cv_url=professor.cv_url,
        personal_website=professor.personal_website,
        department_name=professor.department.name if professor.department else None,
        rmp_rating=professor.instructor.rmp_rating if professor.instructor else None,
        rmp_difficulty=professor.instructor.rmp_difficulty if professor.instructor else None,
        rmp_num_ratings=professor.instructor.rmp_num_ratings if professor.instructor else None,
        claim_status=professor.claim_status or "unclaimed",
        is_claimed=professor.claim_status == "approved",
    )


@router.get("/{instructor_id}/courses", response_model=list[ProfessorCourseResponse])
async def get_instructor_courses(
    instructor_id: int,
    db: Session = Depends(get_db),
):
    """Get courses taught by instructor."""
    professor = db.get(Professor, instructor_id)
    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    courses = db.execute(
        select(ProfessorCourse)
        .options(joinedload(ProfessorCourse.bulletin_course))
        .where(ProfessorCourse.professor_id == instructor_id)
        .order_by(ProfessorCourse.course_code)
    ).scalars().all()

    return [
        ProfessorCourseResponse(
            course_code=c.course_code,
            title=c.bulletin_course.title if c.bulletin_course else None,
            semesters_taught=c.semesters_taught,
            times_taught=c.times_taught,
        )
        for c in courses
    ]


@router.get("/{instructor_id}/syllabi", response_model=list[SyllabusResponse])
async def get_instructor_syllabi(
    instructor_id: int,
    db: Session = Depends(get_db),
):
    """Get syllabi associated with instructor."""
    from sqlalchemy import text

    professor = db.get(Professor, instructor_id)
    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    # Match syllabi by instructor name using raw SQL
    result = db.execute(
        text("""
            SELECT id, course_code, course_title, semester, instructor_name, content, syllabus_url
            FROM syllabi
            WHERE instructor_name ILIKE :name
            ORDER BY semester DESC
            LIMIT 20
        """),
        {"name": f"%{professor.last_name}%"}
    )
    rows = result.fetchall()

    return [
        SyllabusResponse(
            id=row[0],
            course_code=row[1],
            course_title=row[2],
            semester=row[3],
            instructor_name=row[4],
            has_content=row[5] is not None and len(row[5]) > 0 if row[5] else False,
            syllabus_url=row[6],
        )
        for row in rows
    ]


@router.post("/{instructor_id}/claim", response_model=ClaimProfileResponse)
async def claim_instructor_profile(
    instructor_id: int,
    request: ClaimProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a claim request for an instructor profile.

    Requires authentication. Email must be @uga.edu.
    Claim will be manually reviewed and approved.
    """
    professor = db.get(Professor, instructor_id)
    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    # Validate email domain
    email = request.email.lower().strip()
    if not email.endswith("@uga.edu"):
        raise HTTPException(
            status_code=400,
            detail="Email must be a @uga.edu address"
        )

    # Check if already claimed
    if professor.claim_status == "approved":
        raise HTTPException(
            status_code=400,
            detail="This profile has already been claimed"
        )

    # Check if user already has a pending claim for this profile
    if professor.claim_status == "pending" and professor.claimed_by_user_id == user.id:
        return ClaimProfileResponse(
            success=True,
            message="Your claim request is pending review",
            claim_status="pending"
        )

    # Submit claim request
    professor.claimed_by_user_id = user.id
    professor.claim_email = email
    professor.claim_status = "pending"
    professor.claimed_at = datetime.utcnow()

    db.commit()

    return ClaimProfileResponse(
        success=True,
        message="Claim request submitted. We'll verify your email and approve your profile.",
        claim_status="pending"
    )


@router.put("/{instructor_id}/profile", response_model=ProfessorResponse)
async def update_instructor_profile(
    instructor_id: int,
    updates: ProfessorProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update instructor profile.

    Only the user who claimed the profile can update it.
    """
    professor = db.execute(
        select(Professor)
        .options(joinedload(Professor.department), joinedload(Professor.instructor))
        .where(Professor.id == instructor_id)
    ).scalar_one_or_none()

    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    # Check if user owns this profile
    if professor.claim_status != "approved" or professor.claimed_by_user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to edit this profile"
        )

    # Apply updates
    if updates.office_hours is not None:
        professor.office_hours = updates.office_hours
    if updates.bio is not None:
        professor.bio = updates.bio
    if updates.research_areas is not None:
        professor.research_areas = updates.research_areas
    if updates.personal_website is not None:
        professor.personal_website = updates.personal_website

    db.commit()

    return ProfessorResponse(
        id=professor.id,
        name=professor.name,
        first_name=professor.first_name,
        last_name=professor.last_name,
        title=professor.title,
        email=professor.email,
        phone=professor.phone,
        office_location=professor.office_location,
        office_hours=professor.office_hours,
        photo_url=professor.photo_url,
        profile_url=professor.profile_url,
        bio=professor.bio,
        research_areas=professor.research_areas,
        education=professor.education,
        cv_url=professor.cv_url,
        personal_website=professor.personal_website,
        department_name=professor.department.name if professor.department else None,
        rmp_rating=professor.instructor.rmp_rating if professor.instructor else None,
        rmp_difficulty=professor.instructor.rmp_difficulty if professor.instructor else None,
        rmp_num_ratings=professor.instructor.rmp_num_ratings if professor.instructor else None,
        claim_status=professor.claim_status,
        is_claimed=True,
    )


# Admin endpoint to approve claims (for manual verification)
@router.post("/{instructor_id}/approve-claim", response_model=ClaimProfileResponse)
async def approve_claim(
    instructor_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Approve a pending claim request.

    TODO: Add admin check - for now any authenticated user can approve.
    """
    professor = db.get(Professor, instructor_id)
    if not professor:
        raise HTTPException(status_code=404, detail="Instructor not found")

    if professor.claim_status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Profile is not pending approval (status: {professor.claim_status})"
        )

    professor.claim_status = "approved"
    db.commit()

    return ClaimProfileResponse(
        success=True,
        message="Profile claim approved",
        claim_status="approved"
    )
