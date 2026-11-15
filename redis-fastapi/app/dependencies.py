from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.rate_limiter import RateLimiter
from app.services.redis_service import RedisService


def get_redis_service(request: Request) -> RedisService:
    redis_client = request.app.state.redis
    return RedisService(redis_client)


def get_rate_limiter(request: Request) -> RateLimiter:
    redis_client = request.app.state.redis
    return RateLimiter(redis_client)


RedisDependency = Annotated[RedisService, Depends(get_redis_service)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_db)]
RateLimiterDependency = Annotated[RateLimiter, Depends(get_rate_limiter)]
