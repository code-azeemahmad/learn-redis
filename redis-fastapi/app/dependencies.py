from fastapi import Request
from app.services.redis_service import RedisService


def get_redis_service(request: Request) -> RedisService:
    redis_client = request.app.state.redis
    return RedisService(redis_client)
