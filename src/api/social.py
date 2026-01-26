"""
Social API Router.

Handles:
- Following/unfollowing users
- Liking/unliking user profiles
- Liking/unliking instructor profiles
- Getting follower/following lists
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func

from src.api.auth import get_current_user, get_optional_user
from src.api.schemas import (
    FollowResponse,
    UserFollowStats,
    ProfileLikeStats,
)
from src.models.database import (
    User, Instructor, UserFollow, ProfileLike,
    get_session_factory,
)

router = APIRouter(prefix="/social", tags=["social"])


def require_verified(user: User):
    """Ensure user has verified UGA email."""
    if not user.uga_email_verified:
        raise HTTPException(
            status_code=403,
            detail="You must verify your UGA email to use social features"
        )


# =============================================================================
# Follow Endpoints
# =============================================================================

@router.post("/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    user: User = Depends(get_current_user),
):
    """Follow another user."""
    require_verified(user)

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot follow yourself")

    session_factory = get_session_factory()

    with session_factory() as session:
        # Check target user exists and is verified
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        if not target.uga_email_verified:
            raise HTTPException(status_code=400, detail="Cannot follow unverified users")

        # Check if already following
        existing = session.execute(
            select(UserFollow).where(
                UserFollow.follower_id == user.id,
                UserFollow.following_id == user_id
            )
        ).scalar_one_or_none()

        if existing:
            return {"success": True, "message": "Already following"}

        # Create follow
        follow = UserFollow(
            follower_id=user.id,
            following_id=user_id,
        )
        session.add(follow)
        session.commit()

        return {"success": True, "message": "Now following user"}


@router.delete("/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    user: User = Depends(get_current_user),
):
    """Unfollow a user."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        follow = session.execute(
            select(UserFollow).where(
                UserFollow.follower_id == user.id,
                UserFollow.following_id == user_id
            )
        ).scalar_one_or_none()

        if not follow:
            return {"success": True, "message": "Not following"}

        session.delete(follow)
        session.commit()

        return {"success": True, "message": "Unfollowed user"}


@router.get("/users/{user_id}/followers", response_model=list[FollowResponse])
async def get_followers(
    user_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get list of users following this user."""
    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        follows = session.execute(
            select(UserFollow)
            .where(UserFollow.following_id == user_id)
            .order_by(UserFollow.created_at.desc())
        ).scalars().all()

        result = []
        for follow in follows:
            follower = session.get(User, follow.follower_id)
            if follower:
                result.append(FollowResponse(
                    id=follow.id,
                    user_id=follower.id,
                    username=follower.username,
                    first_name=follower.first_name,
                    photo_url=follower.photo_url,
                    created_at=follow.created_at,
                ))

        return result


@router.get("/users/{user_id}/following", response_model=list[FollowResponse])
async def get_following(
    user_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get list of users this user follows."""
    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        follows = session.execute(
            select(UserFollow)
            .where(UserFollow.follower_id == user_id)
            .order_by(UserFollow.created_at.desc())
        ).scalars().all()

        result = []
        for follow in follows:
            following = session.get(User, follow.following_id)
            if following:
                result.append(FollowResponse(
                    id=follow.id,
                    user_id=following.id,
                    username=following.username,
                    first_name=following.first_name,
                    photo_url=following.photo_url,
                    created_at=follow.created_at,
                ))

        return result


@router.get("/users/{user_id}/follow-stats", response_model=UserFollowStats)
async def get_follow_stats(
    user_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get follower/following counts for a user."""
    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        # Count followers
        follower_count = session.execute(
            select(func.count()).select_from(UserFollow)
            .where(UserFollow.following_id == user_id)
        ).scalar() or 0

        # Count following
        following_count = session.execute(
            select(func.count()).select_from(UserFollow)
            .where(UserFollow.follower_id == user_id)
        ).scalar() or 0

        # Check if current user follows
        is_following = False
        if user:
            is_following = session.execute(
                select(UserFollow).where(
                    UserFollow.follower_id == user.id,
                    UserFollow.following_id == user_id
                )
            ).scalar_one_or_none() is not None

        return UserFollowStats(
            follower_count=follower_count,
            following_count=following_count,
            is_following=is_following,
        )


# =============================================================================
# Like Endpoints - User Profiles
# =============================================================================

@router.post("/users/{user_id}/like")
async def like_user(
    user_id: int,
    user: User = Depends(get_current_user),
):
    """Like a user's profile."""
    require_verified(user)

    if user_id == user.id:
        raise HTTPException(status_code=400, detail="You cannot like your own profile")

    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if already liked
        existing = session.execute(
            select(ProfileLike).where(
                ProfileLike.user_id == user.id,
                ProfileLike.target_user_id == user_id
            )
        ).scalar_one_or_none()

        if existing:
            return {"success": True, "message": "Already liked"}

        # Create like
        like = ProfileLike(
            user_id=user.id,
            target_user_id=user_id,
        )
        session.add(like)
        session.commit()

        return {"success": True, "message": "Profile liked"}


@router.delete("/users/{user_id}/like")
async def unlike_user(
    user_id: int,
    user: User = Depends(get_current_user),
):
    """Unlike a user's profile."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        like = session.execute(
            select(ProfileLike).where(
                ProfileLike.user_id == user.id,
                ProfileLike.target_user_id == user_id
            )
        ).scalar_one_or_none()

        if not like:
            return {"success": True, "message": "Not liked"}

        session.delete(like)
        session.commit()

        return {"success": True, "message": "Profile unliked"}


@router.get("/users/{user_id}/like-stats", response_model=ProfileLikeStats)
async def get_user_like_stats(
    user_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get like count for a user profile."""
    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found")

        # Count likes
        like_count = session.execute(
            select(func.count()).select_from(ProfileLike)
            .where(ProfileLike.target_user_id == user_id)
        ).scalar() or 0

        # Check if current user liked
        is_liked = False
        if user:
            is_liked = session.execute(
                select(ProfileLike).where(
                    ProfileLike.user_id == user.id,
                    ProfileLike.target_user_id == user_id
                )
            ).scalar_one_or_none() is not None

        return ProfileLikeStats(
            like_count=like_count,
            is_liked=is_liked,
        )


# =============================================================================
# Like Endpoints - Instructor Profiles
# =============================================================================

@router.post("/instructors/{instructor_id}/like")
async def like_instructor(
    instructor_id: int,
    user: User = Depends(get_current_user),
):
    """Like an instructor's profile."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(Instructor, instructor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Instructor not found")

        # Check if already liked
        existing = session.execute(
            select(ProfileLike).where(
                ProfileLike.user_id == user.id,
                ProfileLike.target_instructor_id == instructor_id
            )
        ).scalar_one_or_none()

        if existing:
            return {"success": True, "message": "Already liked"}

        # Create like
        like = ProfileLike(
            user_id=user.id,
            target_instructor_id=instructor_id,
        )
        session.add(like)
        session.commit()

        return {"success": True, "message": "Instructor liked"}


@router.delete("/instructors/{instructor_id}/like")
async def unlike_instructor(
    instructor_id: int,
    user: User = Depends(get_current_user),
):
    """Unlike an instructor's profile."""
    require_verified(user)

    session_factory = get_session_factory()

    with session_factory() as session:
        like = session.execute(
            select(ProfileLike).where(
                ProfileLike.user_id == user.id,
                ProfileLike.target_instructor_id == instructor_id
            )
        ).scalar_one_or_none()

        if not like:
            return {"success": True, "message": "Not liked"}

        session.delete(like)
        session.commit()

        return {"success": True, "message": "Instructor unliked"}


@router.get("/instructors/{instructor_id}/like-stats", response_model=ProfileLikeStats)
async def get_instructor_like_stats(
    instructor_id: int,
    user: Optional[User] = Depends(get_optional_user),
):
    """Get like count for an instructor profile."""
    session_factory = get_session_factory()

    with session_factory() as session:
        target = session.get(Instructor, instructor_id)
        if not target:
            raise HTTPException(status_code=404, detail="Instructor not found")

        # Count likes
        like_count = session.execute(
            select(func.count()).select_from(ProfileLike)
            .where(ProfileLike.target_instructor_id == instructor_id)
        ).scalar() or 0

        # Check if current user liked
        is_liked = False
        if user:
            is_liked = session.execute(
                select(ProfileLike).where(
                    ProfileLike.user_id == user.id,
                    ProfileLike.target_instructor_id == instructor_id
                )
            ).scalar_one_or_none() is not None

        return ProfileLikeStats(
            like_count=like_count,
            is_liked=is_liked,
        )
