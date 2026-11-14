from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.redis_service import RedisService


def get_redis_service(request: Request) -> RedisService:
    redis_client = request.app.state.redis
    return RedisService(redis_client)


RedisDependency = Annotated[RedisService, Depends(get_redis_service)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_db)]
