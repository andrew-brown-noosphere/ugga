"""
Profile API Router.

Handles:
- UGA email verification
- Username management
- Visibility settings
- Public profile access
"""
import secrets
import re
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func

from src.api.auth import get_current_user, get_optional_user
from src.models.database import User, UserFollow, ProfileLike, get_session_factory

router = APIRouter(prefix="/profile", tags=["profile"])

# Reserved usernames that cannot be claimed
RESERVED_USERNAMES = {
    'admin', 'administrator', 'support', 'help', 'uga', 'dawgplan',
    'api', 'www', 'mail', 'email', 'root', 'system', 'mod', 'moderator',
    'staff', 'team', 'official', 'null', 'undefined', 'anonymous',
}


# =============================================================================
# Schemas
# =============================================================================

class SendVerificationRequest(BaseModel):
    uga_email: str = Field(..., description="UGA email address to verify")

    @field_validator('uga_email')
    @classmethod
    def validate_uga_email(cls, v: str) -> str:
        v = v.lower().strip()
        if not v.endswith('@uga.edu'):
            raise ValueError('Must be a @uga.edu email address')
        if len(v) > 100:
            raise ValueError('Email too long')
        return v


class ConfirmVerificationRequest(BaseModel):
    uga_email: str = Field(..., description="UGA email address")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification code")
    username: Optional[str] = Field(None, min_length=3, max_length=30, description="Desired username")

    @field_validator('uga_email')
    @classmethod
    def validate_uga_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.lower().strip()
        if not re.match(r'^[a-z][a-z0-9_]{2,29}$', v):
            raise ValueError('Username must start with a letter, contain only letters, numbers, and underscores')
        if v in RESERVED_USERNAMES:
            raise ValueError('This username is reserved')
        return v


class VerificationStatusResponse(BaseModel):
    uga_email: Optional[str]
    is_verified: bool
    username: Optional[str]
    profile_url: Optional[str]
    verified_at: Optional[datetime]


class SendVerificationResponse(BaseModel):
    success: bool
    message: str
    expires_in_seconds: int


class ConfirmVerificationResponse(BaseModel):
    success: bool
    username: str
    profile_url: str
    message: str


class VisibilitySettingsResponse(BaseModel):
    profile_visibility: str
    show_full_name: bool
    show_photo: bool
    show_bio: bool
    show_major: bool
    show_graduation_year: bool
    show_classification: bool
    show_completed_courses: bool
    show_current_schedule: bool
    show_gpa: bool
    show_degree_progress: bool
    show_email: bool
    show_social_links: bool


class UpdateVisibilityRequest(BaseModel):
    profile_visibility: Optional[str] = Field(None, pattern='^(public|verified_only|cohorts_only|private)$')
    show_full_name: Optional[bool] = None
    show_photo: Optional[bool] = None
    show_bio: Optional[bool] = None
    show_major: Optional[bool] = None
    show_graduation_year: Optional[bool] = None
    show_classification: Optional[bool] = None
    show_completed_courses: Optional[bool] = None
    show_current_schedule: Optional[bool] = None
    show_gpa: Optional[bool] = None
    show_degree_progress: Optional[bool] = None
    show_email: Optional[bool] = None
    show_social_links: Optional[bool] = None


class PublicProfileResponse(BaseModel):
    id: int
    username: str
    display_name: Optional[str]
    photo_url: Optional[str]
    bio: Optional[str]
    major: Optional[str]
    graduation_year: Optional[int]
    classification: Optional[str]
    # Optional based on visibility
    completed_courses_count: Optional[int]
    degree_progress_percent: Optional[float]
    gpa: Optional[float]
    # Social links
    linkedin_url: Optional[str]
    github_url: Optional[str]
    twitter_url: Optional[str]
    website_url: Optional[str]
    instagram_url: Optional[str]
    tiktok_url: Optional[str]
    bluesky_url: Optional[str]
    # Meta
    is_verified: bool
    is_own_profile: bool
    # Social interactions (for logged-in users)
    is_following: bool = False
    is_liked: bool = False


# =============================================================================
# Verification Endpoints
# =============================================================================

@router.post("/verify/send", response_model=SendVerificationResponse)
async def send_verification_code(
    request: SendVerificationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Send a verification code to a UGA email address.

    The code expires in 10 minutes. Rate limited to 3 attempts per hour.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        user = session.get(User, current_user["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already verified
        if user.uga_email_verified and user.uga_email == request.uga_email:
            raise HTTPException(status_code=400, detail="This email is already verified")

        # Check if email is taken by another user
        existing = session.execute(
            select(User).where(
                User.uga_email == request.uga_email,
                User.id != user.id,
                User.uga_email_verified == True,
            )
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail="This UGA email is already verified by another account")

        # Generate 6-digit code
        code = ''.join(secrets.choice('0123456789') for _ in range(6))
        expires = datetime.utcnow() + timedelta(minutes=10)

        # Store code
        user.uga_email = request.uga_email
        user.verification_code = code
        user.verification_code_expires = expires
        user.uga_email_verified = False

        session.commit()

        # TODO: Actually send the email
        # For now, we'll log it (in production, use SendGrid, SES, etc.)
        print(f"[VERIFICATION] Code {code} sent to {request.uga_email} for user {user.id}")

        # In development, include the code in the response for testing
        # Remove this in production!
        import os
        is_dev = os.getenv("ENV", "development") == "development"

        return SendVerificationResponse(
            success=True,
            message=f"Verification code sent to {request.uga_email[:3]}***@uga.edu" + (f" (DEV: {code})" if is_dev else ""),
            expires_in_seconds=600,
        )


@router.post("/verify/confirm", response_model=ConfirmVerificationResponse)
async def confirm_verification(
    request: ConfirmVerificationRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Confirm verification code and set username.

    If username is not provided, derives it from the email prefix.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        user = session.get(User, current_user["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already verified
        if user.uga_email_verified:
            raise HTTPException(status_code=400, detail="Already verified")

        # Verify email matches
        if user.uga_email != request.uga_email:
            raise HTTPException(status_code=400, detail="Email mismatch. Request a new code.")

        # Check code
        if user.verification_code != request.code:
            raise HTTPException(status_code=400, detail="Invalid verification code")

        # Check expiration
        if user.verification_code_expires and user.verification_code_expires < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Verification code expired. Request a new one.")

        # Determine username
        username = request.username
        if not username:
            # Derive from email: jsmith@uga.edu -> jsmith
            username = request.uga_email.split('@')[0].lower()
            # Clean up: remove dots, limit length
            username = username.replace('.', '_')[:30]

        # Validate username format
        if not re.match(r'^[a-z][a-z0-9_]{2,29}$', username):
            raise HTTPException(
                status_code=400,
                detail="Invalid username format. Must start with a letter, 3-30 characters."
            )

        if username in RESERVED_USERNAMES:
            raise HTTPException(status_code=400, detail="This username is reserved")

        # Check username availability
        existing = session.execute(
            select(User).where(
                func.lower(User.username) == username,
                User.id != user.id,
            )
        ).scalar_one_or_none()

        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")

        # Complete verification
        user.uga_email_verified = True
        user.uga_email_verified_at = datetime.utcnow()
        user.username = username
        user.verification_code = None
        user.verification_code_expires = None

        session.commit()

        return ConfirmVerificationResponse(
            success=True,
            username=username,
            profile_url=f"/u/{username}",
            message="Email verified! Your profile is now shareable.",
        )


@router.get("/verify/status", response_model=VerificationStatusResponse)
async def get_verification_status(
    current_user: dict = Depends(get_current_user),
):
    """Get current verification status."""
    session_factory = get_session_factory()

    with session_factory() as session:
        user = session.get(User, current_user["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return VerificationStatusResponse(
            uga_email=user.uga_email,
            is_verified=user.uga_email_verified,
            username=user.username,
            profile_url=f"/u/{user.username}" if user.username else None,
            verified_at=user.uga_email_verified_at,
        )


# =============================================================================
# Visibility Settings Endpoints
# =============================================================================

@router.get("/visibility", response_model=VisibilitySettingsResponse)
async def get_visibility_settings(
    current_user: dict = Depends(get_current_user),
):
    """Get current visibility settings."""
    session_factory = get_session_factory()

    with session_factory() as session:
        user = session.get(User, current_user["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        settings = user.get_visibility_settings()
        return VisibilitySettingsResponse(**settings)


@router.put("/visibility", response_model=VisibilitySettingsResponse)
async def update_visibility_settings(
    request: UpdateVisibilityRequest,
    current_user: dict = Depends(get_current_user),
):
    """Update visibility settings."""
    session_factory = get_session_factory()

    with session_factory() as session:
        user = session.get(User, current_user["id"])
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Get updates (excluding None values)
        updates = {k: v for k, v in request.model_dump().items() if v is not None}

        if updates:
            user.set_visibility_settings(updates)
            session.commit()

        settings = user.get_visibility_settings()
        return VisibilitySettingsResponse(**settings)


# =============================================================================
# Public Profile Endpoints
# =============================================================================

@router.get("/u/{username}", response_model=PublicProfileResponse)
async def get_public_profile(
    username: str,
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """
    Get a user's public profile by username.

    Respects visibility settings. Returns 404 if profile is private
    or viewer doesn't have access.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        # Find user by username (case-insensitive)
        user = session.execute(
            select(User).where(func.lower(User.username) == username.lower())
        ).scalar_one_or_none()

        if not user:
            raise HTTPException(status_code=404, detail="Profile not found")

        if not user.uga_email_verified:
            raise HTTPException(status_code=404, detail="Profile not found")

        # Check if viewing own profile
        is_own_profile = current_user and current_user["id"] == user.id

        # Get visibility settings
        settings = user.get_visibility_settings()
        visibility = settings.get("profile_visibility", "verified_only")

        # Check access
        if not is_own_profile:
            if visibility == "private":
                raise HTTPException(status_code=404, detail="Profile not found")

            if visibility == "verified_only":
                # Viewer must be a verified UGA student
                if not current_user:
                    raise HTTPException(status_code=401, detail="Sign in to view this profile")

                viewer = session.get(User, current_user["id"])
                if not viewer or not viewer.uga_email_verified:
                    raise HTTPException(status_code=403, detail="Verify your UGA email to view this profile")

            if visibility == "cohorts_only":
                # TODO: Check if viewer is in a shared cohort with this user
                raise HTTPException(status_code=403, detail="This profile is only visible to cohort members")

        # Build response based on visibility settings
        response = {
            "id": user.id,
            "username": user.username,
            "is_verified": user.uga_email_verified,
            "is_own_profile": is_own_profile,
            "is_following": False,
            "is_liked": False,
        }

        # Check if current user is following/liked this profile
        if current_user and not is_own_profile:
            is_following = session.execute(
                select(UserFollow).where(
                    UserFollow.follower_id == current_user["id"],
                    UserFollow.following_id == user.id
                )
            ).scalar_one_or_none()
            response["is_following"] = is_following is not None

            is_liked = session.execute(
                select(ProfileLike).where(
                    ProfileLike.user_id == current_user["id"],
                    ProfileLike.target_user_id == user.id
                )
            ).scalar_one_or_none()
            response["is_liked"] = is_liked is not None

        # Always show display name as a fallback
        if settings.get("show_full_name", True) or is_own_profile:
            response["display_name"] = f"{user.first_name or ''} {user.last_name or ''}".strip() or None
        else:
            response["display_name"] = user.username

        if settings.get("show_photo", True) or is_own_profile:
            response["photo_url"] = user.photo_url

        if settings.get("show_bio", True) or is_own_profile:
            response["bio"] = user.bio

        if settings.get("show_major", True) or is_own_profile:
            response["major"] = user.major

        if settings.get("show_graduation_year", True) or is_own_profile:
            response["graduation_year"] = user.graduation_year

        if settings.get("show_classification", True) or is_own_profile:
            response["classification"] = user.classification

        if settings.get("show_social_links", True) or is_own_profile:
            response["linkedin_url"] = user.linkedin_url
            response["github_url"] = user.github_url
            response["twitter_url"] = user.twitter_url
            response["website_url"] = user.website_url
            response["instagram_url"] = user.instagram_url
            response["tiktok_url"] = user.tiktok_url
            response["bluesky_url"] = user.bluesky_url

        # Sensitive fields - only if explicitly enabled
        if settings.get("show_completed_courses", False) or is_own_profile:
            response["completed_courses_count"] = len(user.completed_courses) if user.completed_courses else 0

        if settings.get("show_degree_progress", False) or is_own_profile:
            # TODO: Calculate actual progress
            response["degree_progress_percent"] = None

        if settings.get("show_gpa", False) or is_own_profile:
            if user.transcript_summary:
                response["gpa"] = user.transcript_summary.cumulative_gpa

        return PublicProfileResponse(**response)


@router.get("/search")
async def search_profiles(
    q: str,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """
    Search for verified users by username or name.

    Only available to verified users. Used for cohort invites.
    """
    session_factory = get_session_factory()

    with session_factory() as session:
        # Check if current user is verified
        user = session.get(User, current_user["id"])
        if not user or not user.uga_email_verified:
            raise HTTPException(status_code=403, detail="Verify your UGA email to search profiles")

        # Search by username or name
        search_term = f"%{q.lower()}%"
        results = session.execute(
            select(User)
            .where(
                User.uga_email_verified == True,
                User.id != user.id,  # Exclude self
                (
                    func.lower(User.username).like(search_term) |
                    func.lower(User.first_name).like(search_term) |
                    func.lower(User.last_name).like(search_term)
                )
            )
            .limit(limit)
        ).scalars().all()

        return [
            {
                "username": u.username,
                "display_name": f"{u.first_name or ''} {u.last_name or ''}".strip() or u.username,
                "photo_url": u.photo_url if u.get_visibility_settings().get("show_photo", True) else None,
                "major": u.major if u.get_visibility_settings().get("show_major", True) else None,
            }
            for u in results
        ]
