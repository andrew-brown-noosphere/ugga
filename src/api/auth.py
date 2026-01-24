"""
Clerk authentication dependencies for FastAPI.

Provides JWT verification and user lookup from Clerk tokens.
"""
from typing import Optional
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
import httpx

from src.config import settings
from src.models.database import User, get_session_factory


async def verify_clerk_token(authorization: str = Header(...)) -> dict:
    """
    Verify Clerk JWT token and return session claims.

    Uses Clerk's Backend API to verify the session token.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    if not settings.clerk_secret_key:
        raise HTTPException(status_code=500, detail="Clerk not configured")

    # Verify with Clerk Backend API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.clerk.com/v1/tokens/verify",
            headers={
                "Authorization": f"Bearer {settings.clerk_secret_key}",
                "Content-Type": "application/json",
            },
            json={"token": token}
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return response.json()


async def get_current_user(
    claims: dict = Depends(verify_clerk_token),
) -> User:
    """
    Get current user from database based on Clerk token.

    If user doesn't exist (webhook hasn't synced yet), creates them from token claims.
    """
    clerk_id = claims.get("sub")
    if not clerk_id:
        raise HTTPException(status_code=401, detail="Invalid token claims")

    session_factory = get_session_factory()
    with session_factory() as session:
        user = session.execute(
            select(User).where(User.clerk_id == clerk_id)
        ).scalar_one_or_none()

        if not user:
            # Auto-create user from token claims (handles case where webhook hasn't synced)
            # Get email from claims (Clerk includes this in the token)
            email = claims.get("email") or claims.get("primary_email_address") or f"{clerk_id}@clerk.placeholder"
            first_name = claims.get("first_name")
            last_name = claims.get("last_name")

            user = User(
                clerk_id=clerk_id,
                email=email,
                first_name=first_name,
                last_name=last_name,
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        # Detach from session so it can be used after session closes
        session.expunge(user)
        return user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    Useful for endpoints that work for both authenticated and anonymous users.
    """
    if not authorization:
        return None

    try:
        claims = await verify_clerk_token(authorization)
        return await get_current_user(claims)
    except HTTPException:
        return None
