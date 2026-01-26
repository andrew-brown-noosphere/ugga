"""
Cohorts API Router.

Handles:
- Creating and managing cohorts (friend groups for schedule coordination)
- Joining via invite code
- Leaving cohorts
- Listing cohort members
"""
import secrets
import string
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from src.api.auth import get_current_user
from src.api.schemas import (
    CohortResponse,
    CohortCreateRequest,
    CohortUpdateRequest,
    CohortJoinRequest,
    CohortMemberResponse,
)
from src.models.database import (
    User, Cohort, CohortMember,
    get_session_factory,
)

router = APIRouter(prefix="/cohorts", tags=["cohorts"])


def require_verified(user: User):
    """Ensure user has verified UGA email."""
    if not user.uga_email_verified:
        raise HTTPException(
            status_code=403,
            detail="You must verify your UGA email to use social features"
        )


def generate_invite_code(length: int = 8) -> str:
    """Generate a random invite code."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def get_cohort_response(
    cohort: Cohort,
    member_count: int,
    current_user_id: int,
    user_role: Optional[str] = None
) -> CohortResponse:
    """Convert Cohort to response with computed fields."""
    is_member = False
    is_admin = False

    if user_role:
        is_member = True
        is_admin = user_role == "admin"
    else:
        # Check membership
        for member in cohort.members:
            if member.user_id == current_user_id:
                is_member = True
                is_admin = member.role == "admin"
                break

    return CohortResponse(
        id=cohort.id,
        name=cohort.name,
        description=cohort.description,
        created_by_id=cohort.created_by_id,
        created_by_username=cohort.created_by.username if cohort.created_by else None,
        is_public=cohort.is_public,
        max_members=cohort.max_members,
        invite_code=cohort.invite_code if is_member else None,  # Only show to members
        member_count=member_count,
        is_member=is_member,
        is_admin=is_admin,
        created_at=cohort.created_at,
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=list[CohortResponse])
async def list_my_cohorts(
    user: User = Depends(get_current_user),
):
    """List cohorts the current user belongs to."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        # Get all cohorts where user is a member
        query = (
            select(Cohort, CohortMember.role)
            .join(CohortMember, CohortMember.cohort_id == Cohort.id)
            .where(CohortMember.user_id == user.id)
            .order_by(Cohort.created_at.desc())
        )
        results = session.execute(query).all()

        response = []
        for cohort, role in results:
            member_count = len(cohort.members)
            response.append(get_cohort_response(cohort, member_count, user.id, role))

        return response


@router.post("", response_model=CohortResponse)
async def create_cohort(
    request: CohortCreateRequest,
    user: User = Depends(get_current_user),
):
    """Create a new cohort. Creator becomes admin."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        # Generate unique invite code
        invite_code = generate_invite_code()
        while session.execute(
            select(Cohort).where(Cohort.invite_code == invite_code)
        ).scalar_one_or_none():
            invite_code = generate_invite_code()

        # Create cohort
        cohort = Cohort(
            name=request.name,
            description=request.description,
            created_by_id=user.id,
            is_public=request.is_public,
            max_members=request.max_members,
            invite_code=invite_code,
        )
        session.add(cohort)
        session.flush()

        # Add creator as admin member
        membership = CohortMember(
            cohort_id=cohort.id,
            user_id=user.id,
            role="admin",
        )
        session.add(membership)
        session.commit()

        session.refresh(cohort)

        return get_cohort_response(cohort, 1, user.id, "admin")


@router.get("/{cohort_id}", response_model=CohortResponse)
async def get_cohort(
    cohort_id: int,
    user: User = Depends(get_current_user),
):
    """Get cohort details. Must be a member to view."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check membership
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if not membership and not cohort.is_public:
            raise HTTPException(status_code=403, detail="You must be a member to view this cohort")

        member_count = len(cohort.members)
        return get_cohort_response(
            cohort,
            member_count,
            user.id,
            membership.role if membership else None
        )


@router.get("/{cohort_id}/members", response_model=list[CohortMemberResponse])
async def get_cohort_members(
    cohort_id: int,
    user: User = Depends(get_current_user),
):
    """Get cohort members. Must be a member."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check membership
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=403, detail="You must be a member to view members")

        result = []
        for member in cohort.members:
            result.append(CohortMemberResponse(
                id=member.id,
                user_id=member.user_id,
                username=member.user.username if member.user else None,
                first_name=member.user.first_name if member.user else None,
                photo_url=member.user.photo_url if member.user else None,
                role=member.role,
                joined_at=member.joined_at,
            ))

        return result


@router.put("/{cohort_id}", response_model=CohortResponse)
async def update_cohort(
    cohort_id: int,
    request: CohortUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update cohort. Admin only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check admin
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id,
                CohortMember.role == "admin"
            )
        ).scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=403, detail="Only admins can update this cohort")

        # Update fields
        if request.name is not None:
            cohort.name = request.name
        if request.description is not None:
            cohort.description = request.description
        if request.is_public is not None:
            cohort.is_public = request.is_public
        if request.max_members is not None:
            cohort.max_members = request.max_members

        session.commit()
        session.refresh(cohort)

        member_count = len(cohort.members)
        return get_cohort_response(cohort, member_count, user.id, "admin")


@router.delete("/{cohort_id}")
async def delete_cohort(
    cohort_id: int,
    user: User = Depends(get_current_user),
):
    """Delete cohort. Admin only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check admin
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id,
                CohortMember.role == "admin"
            )
        ).scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=403, detail="Only admins can delete this cohort")

        session.delete(cohort)
        session.commit()

        return {"success": True, "message": "Cohort deleted"}


@router.post("/join", response_model=CohortResponse)
async def join_cohort_by_code(
    request: CohortJoinRequest,
    user: User = Depends(get_current_user),
):
    """Join a cohort using an invite code."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        # Find cohort by invite code
        cohort = session.execute(
            select(Cohort).where(Cohort.invite_code == request.invite_code.upper())
        ).scalar_one_or_none()

        if not cohort:
            raise HTTPException(status_code=404, detail="Invalid invite code")

        # Check if already a member
        existing = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort.id,
                CohortMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if existing:
            member_count = len(cohort.members)
            return get_cohort_response(cohort, member_count, user.id, existing.role)

        # Check member limit
        member_count = len(cohort.members)
        if member_count >= cohort.max_members:
            raise HTTPException(status_code=400, detail="Cohort is full")

        # Join
        membership = CohortMember(
            cohort_id=cohort.id,
            user_id=user.id,
            role="member",
        )
        session.add(membership)
        session.commit()

        session.refresh(cohort)
        member_count = len(cohort.members)
        return get_cohort_response(cohort, member_count, user.id, "member")


@router.post("/{cohort_id}/leave")
async def leave_cohort(
    cohort_id: int,
    user: User = Depends(get_current_user),
):
    """Leave a cohort."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Find membership
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if not membership:
            return {"success": True, "message": "Not a member"}

        # Check if last admin
        if membership.role == "admin":
            admin_count = session.execute(
                select(CohortMember).where(
                    CohortMember.cohort_id == cohort_id,
                    CohortMember.role == "admin"
                )
            ).scalars().all()

            if len(admin_count) == 1:
                raise HTTPException(
                    status_code=400,
                    detail="You're the last admin. Promote another member or delete the cohort."
                )

        session.delete(membership)
        session.commit()

        return {"success": True, "message": "Left cohort"}


@router.post("/{cohort_id}/promote/{user_id}")
async def promote_member(
    cohort_id: int,
    user_id: int,
    user: User = Depends(get_current_user),
):
    """Promote a member to admin. Admin only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check current user is admin
        my_membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id,
                CohortMember.role == "admin"
            )
        ).scalar_one_or_none()

        if not my_membership:
            raise HTTPException(status_code=403, detail="Only admins can promote members")

        # Find target membership
        target_membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user_id
            )
        ).scalar_one_or_none()

        if not target_membership:
            raise HTTPException(status_code=404, detail="User is not a member")

        if target_membership.role == "admin":
            return {"success": True, "message": "User is already an admin"}

        target_membership.role = "admin"
        session.commit()

        return {"success": True, "message": "Member promoted to admin"}


@router.post("/{cohort_id}/regenerate-code")
async def regenerate_invite_code(
    cohort_id: int,
    user: User = Depends(get_current_user),
):
    """Generate a new invite code. Admin only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        cohort = session.get(Cohort, cohort_id)
        if not cohort:
            raise HTTPException(status_code=404, detail="Cohort not found")

        # Check admin
        membership = session.execute(
            select(CohortMember).where(
                CohortMember.cohort_id == cohort_id,
                CohortMember.user_id == user.id,
                CohortMember.role == "admin"
            )
        ).scalar_one_or_none()

        if not membership:
            raise HTTPException(status_code=403, detail="Only admins can regenerate invite code")

        # Generate new code
        new_code = generate_invite_code()
        while session.execute(
            select(Cohort).where(Cohort.invite_code == new_code)
        ).scalar_one_or_none():
            new_code = generate_invite_code()

        cohort.invite_code = new_code
        session.commit()

        return {"success": True, "invite_code": new_code}
