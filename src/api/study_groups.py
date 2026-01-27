"""
Study Groups API Router.

Handles:
- Creating and managing study groups
- Joining/leaving study groups
- Listing study groups by course
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func

from src.api.auth import get_current_user, get_optional_user
from src.api.schemas import (
    StudyGroupResponse,
    StudyGroupCreateRequest,
    StudyGroupUpdateRequest,
    StudyGroupMemberResponse,
)
from src.models.database import (
    User, StudyGroup, StudyGroupMember,
    get_session_factory,
)

router = APIRouter(prefix="/study-groups", tags=["study-groups"])


def require_verified(user: User):
    """Ensure user has verified UGA email."""
    if not user.uga_email_verified:
        raise HTTPException(
            status_code=403,
            detail="You must verify your UGA email to use social features"
        )


def get_study_group_response(
    group: StudyGroup,
    member_count: int,
    current_user_id: Optional[int] = None
) -> StudyGroupResponse:
    """Convert StudyGroup to response with computed fields."""
    is_member = False
    is_organizer = False

    if current_user_id:
        is_organizer = group.organizer_id == current_user_id
        for member in group.members:
            if member.user_id == current_user_id:
                is_member = True
                break

    return StudyGroupResponse(
        id=group.id,
        course_code=group.course_code,
        name=group.name,
        description=group.description,
        meeting_day=group.meeting_day,
        meeting_time=group.meeting_time,
        meeting_location=group.meeting_location,
        organizer_id=group.organizer_id,
        organizer_username=group.organizer.username if group.organizer else None,
        organizer_first_name=group.organizer.first_name if group.organizer else None,
        max_members=group.max_members,
        member_count=member_count,
        is_active=group.is_active,
        is_official=group.is_official,
        is_claimable=group.organizer_id is None,
        is_member=is_member,
        is_organizer=is_organizer,
        created_at=group.created_at,
    )


# =============================================================================
# Endpoints
# =============================================================================

@router.get("", response_model=list[StudyGroupResponse])
async def list_study_groups(
    course_code: Optional[str] = Query(None, description="Filter by course code"),
    active_only: bool = Query(True, description="Only show active groups"),
    limit: int = Query(50, ge=1, le=100),
    user: Optional[User] = Depends(get_optional_user),
):
    """List study groups, optionally filtered by course."""
    session_factory = get_session_factory()

    with session_factory() as session:
        query = select(StudyGroup)

        if course_code:
            query = query.where(StudyGroup.course_code == course_code.upper().replace(" ", ""))

        if active_only:
            query = query.where(StudyGroup.is_active == True)

        query = query.order_by(StudyGroup.created_at.desc()).limit(limit)
        groups = session.execute(query).scalars().all()

        result = []
        for group in groups:
            member_count = len(group.members)
            result.append(get_study_group_response(
                group,
                member_count,
                user.id if user else None
            ))

        return result


@router.post("", response_model=StudyGroupResponse)
async def create_study_group(
    request: StudyGroupCreateRequest,
    user: User = Depends(get_current_user),
):
    """Create a new study group. Creator becomes the organizer."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        # Create the group
        group = StudyGroup(
            course_code=request.course_code.upper().replace(" ", ""),
            name=request.name,
            description=request.description,
            meeting_day=request.meeting_day,
            meeting_time=request.meeting_time,
            meeting_location=request.meeting_location,
            organizer_id=user.id,
            max_members=request.max_members,
        )
        session.add(group)
        session.flush()

        # Add organizer as a member
        membership = StudyGroupMember(
            study_group_id=group.id,
            user_id=user.id,
        )
        session.add(membership)
        session.commit()

        # Refresh to get relationships
        session.refresh(group)

        return get_study_group_response(group, 1, user.id)


@router.get("/{group_id}", response_model=StudyGroupResponse)
async def get_study_group(
    group_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get study group details."""
    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        member_count = len(group.members)
        return get_study_group_response(group, member_count, user.id if user else None)


@router.get("/{group_id}/members", response_model=list[StudyGroupMemberResponse])
async def get_study_group_members(
    group_id: int,
    user: User = Depends(get_current_user),
):
    """Get study group members. Requires verified email."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        result = []
        for member in group.members:
            result.append(StudyGroupMemberResponse(
                id=member.id,
                user_id=member.user_id,
                username=member.user.username if member.user else None,
                first_name=member.user.first_name if member.user else None,
                photo_url=member.user.photo_url if member.user else None,
                joined_at=member.joined_at,
            ))

        return result


@router.put("/{group_id}", response_model=StudyGroupResponse)
async def update_study_group(
    group_id: int,
    request: StudyGroupUpdateRequest,
    user: User = Depends(get_current_user),
):
    """Update study group. Organizer only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        if group.organizer_id != user.id:
            raise HTTPException(status_code=403, detail="Only the organizer can update this group")

        # Update fields
        if request.name is not None:
            group.name = request.name
        if request.description is not None:
            group.description = request.description
        if request.meeting_day is not None:
            group.meeting_day = request.meeting_day
        if request.meeting_time is not None:
            group.meeting_time = request.meeting_time
        if request.meeting_location is not None:
            group.meeting_location = request.meeting_location
        if request.max_members is not None:
            group.max_members = request.max_members
        if request.is_active is not None:
            group.is_active = request.is_active

        session.commit()
        session.refresh(group)

        member_count = len(group.members)
        return get_study_group_response(group, member_count, user.id)


@router.delete("/{group_id}")
async def delete_study_group(
    group_id: int,
    user: User = Depends(get_current_user),
):
    """Delete study group. Organizer only."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        if group.organizer_id != user.id:
            raise HTTPException(status_code=403, detail="Only the organizer can delete this group")

        session.delete(group)
        session.commit()

        return {"success": True, "message": "Study group deleted"}


@router.post("/{group_id}/join")
async def join_study_group(
    group_id: int,
    user: User = Depends(get_current_user),
):
    """Join a study group."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        if not group.is_active:
            raise HTTPException(status_code=400, detail="This study group is no longer active")

        # Check if already a member
        existing = session.execute(
            select(StudyGroupMember).where(
                StudyGroupMember.study_group_id == group_id,
                StudyGroupMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if existing:
            return {"success": True, "message": "Already a member"}

        # Check member limit
        member_count = len(group.members)
        if member_count >= group.max_members:
            raise HTTPException(status_code=400, detail="Study group is full")

        # Join
        membership = StudyGroupMember(
            study_group_id=group_id,
            user_id=user.id,
        )
        session.add(membership)
        session.commit()

        return {"success": True, "message": "Joined study group"}


@router.post("/{group_id}/claim")
async def claim_study_group(
    group_id: int,
    user: User = Depends(get_current_user),
):
    """
    Claim an unclaimed study group to become the organizer.

    Only works for groups without an organizer (pre-seeded groups).
    """
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        if group.organizer_id is not None:
            raise HTTPException(status_code=400, detail="This study group already has an organizer")

        # Claim the group
        group.organizer_id = user.id

        # Also add user as a member if not already
        existing_membership = session.execute(
            select(StudyGroupMember).where(
                StudyGroupMember.study_group_id == group_id,
                StudyGroupMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if not existing_membership:
            membership = StudyGroupMember(
                study_group_id=group_id,
                user_id=user.id,
            )
            session.add(membership)

        session.commit()
        session.refresh(group)

        member_count = len(group.members)
        return get_study_group_response(group, member_count, user.id)


@router.post("/{group_id}/leave")
async def leave_study_group(
    group_id: int,
    user: User = Depends(get_current_user),
):
    """Leave a study group."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        group = session.get(StudyGroup, group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Study group not found")

        # Can't leave if you're the organizer
        if group.organizer_id == user.id:
            raise HTTPException(
                status_code=400,
                detail="Organizers cannot leave. Transfer ownership or delete the group."
            )

        # Find membership
        membership = session.execute(
            select(StudyGroupMember).where(
                StudyGroupMember.study_group_id == group_id,
                StudyGroupMember.user_id == user.id
            )
        ).scalar_one_or_none()

        if not membership:
            return {"success": True, "message": "Not a member"}

        session.delete(membership)
        session.commit()

        return {"success": True, "message": "Left study group"}
