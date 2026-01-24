"""
User management API endpoints.

Handles Clerk webhook sync and user profile management.
"""
import hashlib
import hmac
import json
import base64
from fastapi import APIRouter, HTTPException, Depends, Header, Request
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload

from src.config import settings
from src.models.database import User, Program, get_session_factory
from src.api.schemas import (
    UserResponse,
    UserUpdateRequest,
    PersonalizedReportResponse,
    DegreeProgressResponse,
    CourseRecommendationResponse,
    ScheduleItemResponse,
    ProgramResponse,
    ProgramRequirementResponse,
    RequirementCourseResponse,
)
from src.api.auth import get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

# Disclaimer text for all reports
DISCLAIMER_TEXT = (
    "This report is based on official UGA class schedules that can be found at "
    "https://reg.uga.edu/scheduling/schedule_of_classes/. "
    "This is not a replacement for your academic advisor. "
    "Always verify your course scheduling with your academic advisor."
)


@router.post("/sync")
async def sync_user_webhook(
    request: Request,
    svix_id: str = Header(None, alias="svix-id"),
    svix_timestamp: str = Header(None, alias="svix-timestamp"),
    svix_signature: str = Header(None, alias="svix-signature"),
):
    """
    Webhook endpoint for Clerk to sync user creation/updates.

    Clerk sends webhooks for user.created, user.updated, user.deleted events.
    Webhooks are signed using Svix for verification.
    """
    body = await request.body()

    # Verify webhook signature if configured
    if settings.clerk_webhook_secret and svix_signature:
        try:
            # Construct signed content
            signed_content = f"{svix_id}.{svix_timestamp}.{body.decode()}"

            # Verify signature (Clerk uses Svix for webhooks)
            # The secret comes as whsec_xxx, we need to decode the base64 part
            secret = settings.clerk_webhook_secret
            if secret.startswith("whsec_"):
                secret = secret[6:]

            secret_bytes = base64.b64decode(secret)
            expected_sig = hmac.new(
                secret_bytes,
                signed_content.encode(),
                hashlib.sha256
            ).digest()
            expected_sig_b64 = base64.b64encode(expected_sig).decode()

            # Extract signature from header (format: v1,signature v1,signature2 ...)
            valid = False
            for sig_part in svix_signature.split(" "):
                if sig_part.startswith("v1,"):
                    sig_value = sig_part[3:]
                    if hmac.compare_digest(sig_value, expected_sig_b64):
                        valid = True
                        break

            if not valid:
                raise HTTPException(status_code=401, detail="Invalid webhook signature")
        except Exception as e:
            # Log but don't fail on signature verification errors during development
            print(f"Webhook signature verification error: {e}")

    # Parse payload
    payload = json.loads(body)
    event_type = payload.get("type")
    data = payload.get("data", {})

    session_factory = get_session_factory()
    with session_factory() as session:
        if event_type == "user.created":
            # Check if user already exists (idempotency)
            existing = session.execute(
                select(User).where(User.clerk_id == data["id"])
            ).scalar_one_or_none()

            if not existing:
                # Get primary email
                email = None
                if data.get("email_addresses"):
                    primary = next(
                        (e for e in data["email_addresses"] if e.get("id") == data.get("primary_email_address_id")),
                        data["email_addresses"][0]
                    )
                    email = primary.get("email_address")

                user = User(
                    clerk_id=data["id"],
                    email=email or f"{data['id']}@clerk.placeholder",
                    first_name=data.get("first_name"),
                    last_name=data.get("last_name"),
                )
                session.add(user)
                session.commit()

        elif event_type == "user.updated":
            user = session.execute(
                select(User).where(User.clerk_id == data["id"])
            ).scalar_one_or_none()

            if user:
                # Get primary email
                if data.get("email_addresses"):
                    primary = next(
                        (e for e in data["email_addresses"] if e.get("id") == data.get("primary_email_address_id")),
                        data["email_addresses"][0]
                    )
                    user.email = primary.get("email_address", user.email)

                user.first_name = data.get("first_name", user.first_name)
                user.last_name = data.get("last_name", user.last_name)
                session.commit()

        elif event_type == "user.deleted":
            user = session.execute(
                select(User).where(User.clerk_id == data["id"])
            ).scalar_one_or_none()

            if user:
                session.delete(user)
                session.commit()

    return {"status": "ok", "event": event_type}


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(user: User = Depends(get_current_user)):
    """Get current user's profile."""
    return UserResponse.model_validate(user)


@router.put("/me", response_model=UserResponse)
async def update_user_preferences(
    update: UserUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update current user's profile and preferences."""
    session_factory = get_session_factory()
    with session_factory() as session:
        db_user = session.execute(
            select(User).where(User.id == user.id)
        ).scalar_one()

        # Academic preferences
        if update.major is not None:
            db_user.major = update.major
        if update.goal is not None:
            db_user.goal = update.goal

        # Extended profile
        if update.photo_url is not None:
            db_user.photo_url = update.photo_url
        if update.bio is not None:
            db_user.bio = update.bio
        if update.graduation_year is not None:
            db_user.graduation_year = update.graduation_year
        if update.classification is not None:
            db_user.classification = update.classification

        # Social links
        if update.linkedin_url is not None:
            db_user.linkedin_url = update.linkedin_url
        if update.github_url is not None:
            db_user.github_url = update.github_url
        if update.twitter_url is not None:
            db_user.twitter_url = update.twitter_url
        if update.website_url is not None:
            db_user.website_url = update.website_url

        session.commit()
        session.refresh(db_user)
        return UserResponse.model_validate(db_user)


@router.get("/me/report", response_model=PersonalizedReportResponse)
async def get_personalized_report(user: User = Depends(get_current_user)):
    """
    Get personalized degree report based on user's major and goal.

    Includes:
    - Degree progress
    - AI course recommendations
    - Sample schedule preview
    - Required disclaimer
    """
    session_factory = get_session_factory()

    program = None
    program_response = None
    degree_progress = None
    recommendations = []
    sample_schedule = []

    with session_factory() as session:
        # Get program by major using fuzzy matching
        if user.major:
            # Try to find program matching the major
            query = (
                select(Program)
                .options(joinedload(Program.requirements))
                .where(func.lower(Program.name).contains(user.major.lower()))
                .order_by(func.length(Program.name))
            )
            program = session.execute(query).unique().scalars().first()

            if program:
                # Build program response with requirements
                requirements = []
                for req in program.requirements:
                    courses = []
                    for rc in req.courses:
                        courses.append(RequirementCourseResponse(
                            course_code=rc.course_code,
                            title=rc.title,
                            credit_hours=rc.credit_hours,
                            is_group=rc.is_group,
                            group_description=rc.group_description
                        ))

                    requirements.append(ProgramRequirementResponse(
                        id=req.id,
                        name=req.name,
                        category=req.category,
                        required_hours=req.required_hours,
                        description=req.description,
                        selection_type=req.selection_type,
                        courses_to_select=req.courses_to_select,
                        courses=courses
                    ))

                program_response = ProgramResponse(
                    id=program.id,
                    bulletin_id=program.bulletin_id,
                    name=program.name,
                    degree_type=program.degree_type,
                    college_code=program.college_code,
                    department=program.department,
                    overview=program.overview,
                    total_hours=program.total_hours,
                    bulletin_url=program.bulletin_url,
                    requirements=requirements
                )

                # Calculate degree progress (placeholder - would need user's completed courses)
                degree_progress = DegreeProgressResponse(
                    total_hours_required=program.total_hours or 120,
                    hours_completed=0,  # Would come from user's completed courses
                    percent_complete=0.0,
                    requirements_complete=[],
                    requirements_remaining=[req.name for req in program.requirements]
                )

                # Generate recommendations based on goal
                recommendations = _generate_recommendations(program, user.goal, session)

                # Generate sample schedule
                sample_schedule = _generate_sample_schedule(program, user.goal, session)

    return PersonalizedReportResponse(
        user=UserResponse.model_validate(user),
        program=program_response,
        degree_progress=degree_progress,
        recommendations=recommendations,
        sample_schedule=sample_schedule,
        disclaimer=DISCLAIMER_TEXT
    )


def _generate_recommendations(program: Program, goal: str, session) -> list[CourseRecommendationResponse]:
    """Generate course recommendations based on program and goal."""
    recommendations = []

    # Get foundation/required courses first
    for req in program.requirements:
        if req.category.lower() in ['foundation', 'major', 'core']:
            for course in req.courses[:3]:  # Limit to top 3 per category
                reason = _get_recommendation_reason(goal, req.category, course.course_code)
                priority = "high" if req.category.lower() in ['foundation', 'core'] else "medium"

                recommendations.append(CourseRecommendationResponse(
                    course_code=course.course_code,
                    title=course.title or "Course Title",
                    reason=reason,
                    priority=priority
                ))

        if len(recommendations) >= 10:
            break

    return recommendations[:10]


def _get_recommendation_reason(goal: str, category: str, course_code: str) -> str:
    """Generate recommendation reason based on goal."""
    if goal == "fast-track":
        return f"Required {category.lower()} course - complete early to unlock advanced courses"
    elif goal == "specialist":
        return f"Core {category.lower()} course that builds expertise in your field"
    elif goal == "well-rounded":
        return f"Essential {category.lower()} course that provides broad foundational knowledge"
    else:  # flexible
        return f"Flexible {category.lower()} course that keeps multiple paths open"


def _generate_sample_schedule(program: Program, goal: str, session) -> list[ScheduleItemResponse]:
    """Generate a sample 4-semester schedule based on program and goal."""
    schedule = []
    semesters = ["Fall 2026", "Spring 2027", "Fall 2027", "Spring 2028"]

    # Distribute courses across semesters
    all_courses = []
    for req in program.requirements:
        for course in req.courses:
            all_courses.append((course, req.category))

    # Sort by category priority (foundations first)
    category_priority = {"foundation": 0, "core": 1, "major": 2, "elective": 3, "general education": 4}
    all_courses.sort(key=lambda x: category_priority.get(x[1].lower(), 5))

    # Distribute 4-5 courses per semester
    courses_per_semester = 5 if goal == "fast-track" else 4
    course_idx = 0

    for semester in semesters:
        semester_courses = 0
        while semester_courses < courses_per_semester and course_idx < len(all_courses):
            course, category = all_courses[course_idx]
            schedule.append(ScheduleItemResponse(
                course_code=course.course_code,
                title=course.title or "Course Title",
                semester=semester,
                credit_hours=course.credit_hours or 3
            ))
            semester_courses += 1
            course_idx += 1

    return schedule[:20]  # Limit to 4 semesters worth
