"""
Rate limiting for API endpoints.

Uses slowapi for rate limiting with configurable backends:
- In-memory (default): Good for single instance deployments
- Redis: Required for multiple workers/instances

Rate limits are applied per user (authenticated) or per IP (anonymous).
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse

from src.config import settings


def get_identifier(request: Request) -> str:
    """
    Get rate limit identifier - user ID if authenticated, IP otherwise.

    This ensures authenticated users get their own quota while
    anonymous users are limited by IP.
    """
    # Check for user in request state (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        user_id = request.state.user.get("id")
        if user_id:
            return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


def get_storage_uri() -> str:
    """Get storage backend URI - Redis if available, memory otherwise."""
    redis_url = getattr(settings, "redis_url", None)
    if redis_url:
        return redis_url
    return "memory://"


# Create the limiter instance
limiter = Limiter(
    key_func=get_identifier,
    storage_uri=get_storage_uri(),
    default_limits=["200/minute"],  # Default for all endpoints
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "retry_after": exc.detail,
        },
        headers={"Retry-After": str(getattr(exc, "retry_after", 60))},
    )


# Preset rate limit decorators for common use cases
# Usage: @chat_limit (instead of @limiter.limit("10/minute"))

def chat_limit(func):
    """Rate limit for AI chat - expensive API calls."""
    return limiter.limit("20/minute")(limiter.limit("100/hour")(func))


def search_limit(func):
    """Rate limit for search endpoints."""
    return limiter.limit("60/minute")(func)


def write_limit(func):
    """Rate limit for write operations (POST/PUT/DELETE)."""
    return limiter.limit("30/minute")(func)


def auth_limit(func):
    """Rate limit for authentication-related endpoints."""
    return limiter.limit("10/minute")(limiter.limit("50/hour")(func))
