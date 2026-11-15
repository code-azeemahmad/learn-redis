from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.rate_limiter import RateLimiter
from app.services.redis_service import RedisService
from app.services.session_service import SessionService


def get_redis_service(request: Request) -> RedisService:
    redis_client = request.app.state.redis
    return RedisService(redis_client)


def get_rate_limiter(request: Request) -> RateLimiter:
    redis_client = request.app.state.redis
    return RateLimiter(redis_client)


def get_session_service(request: Request) -> SessionService:
    redis_client = request.app.state.redis
    return SessionService(redis_client)


RedisDependency = Annotated[RedisService, Depends(get_redis_service)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_db)]
RateLimiterDependency = Annotated[RateLimiter, Depends(get_rate_limiter)]
SessionDependency = Annotated[SessionService, Depends(get_session_service)]


async def get_current_session(
    request: Request,
    session_service: SessionDependency
) -> dict:
    """
    Validates the session cookie against Redis.
    Fails closed with HTTP 503 if Redis is unreachable (Lesson 21 Section 10).
    """
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    try:
        session = await session_service.get_session(session_id)
    except RedisError:
        # Production Principle: Fail closed when authoritative session store is unavailable
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable"
        )

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    return session


CurrentSession = Annotated[dict, Depends(get_current_session)]
