from typing import Annotated, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.dependencies import get_redis_service
from app.services.redis_service import RedisService

router = APIRouter(
    prefix="/cache",
    tags=["Cache"]
)


class CachePayload(BaseModel):
    value: dict[str, Any]
    ttl_seconds: int = Field(
        default=300,
        gt=0,
        le=86400
    )


class UserPayload(BaseModel):
    username: str
    email: str
    role: str


RedisServiceDependency = Annotated[
    RedisService,
    Depends(get_redis_service)
]


# ==========================================
# Task 1: User Cache Endpoints
# ==========================================

@router.post("/users/{user_id}")
async def set_user_cache(
    user_id: int,
    payload: UserPayload,
    cache: RedisServiceDependency
):
    key = f"user:{user_id}"
    try:
        await cache.set_json(
            key,
            payload.model_dump(),
            ttl=600
        )
        return {
            "message": "User cached successfully",
            "user_id": user_id,
            "key": key,
            "ttl": 600
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


@router.get("/users/{user_id}")
async def get_user_cache(
    user_id: int,
    cache: RedisServiceDependency
):
    key = f"user:{user_id}"
    try:
        user_data = await cache.get_json(key)
        if user_data is None:
            raise HTTPException(
                status_code=404,
                detail="User not found in cache"
            )
        return {
            "user_id": user_id,
            "user": user_data
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


@router.delete("/users/{user_id}")
async def delete_user_cache(
    user_id: int,
    cache: RedisServiceDependency
):
    key = f"user:{user_id}"
    try:
        deleted = await cache.delete(key)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="User not found in cache"
            )
        return {
            "message": "User cache deleted successfully",
            "user_id": user_id
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


# ==========================================
# Task 2: Exists Check Endpoint
# ==========================================

@router.get("/{key}/exists")
async def check_cache_exists(
    key: str,
    cache: RedisServiceDependency
):
    try:
        exists = await cache.exists(key)
        return {
            "key": key,
            "exists": exists
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


# ==========================================
# General Cache Endpoints
# ==========================================

@router.post("/{key}")
async def set_cache(
    key: str,
    payload: CachePayload,
    cache: RedisServiceDependency
):
    try:
        await cache.set_json(
            key,
            payload.value,
            ttl=payload.ttl_seconds
        )
        return {
            "message": "Cache stored successfully",
            "key": key,
            "ttl": payload.ttl_seconds
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


@router.get("/{key}")
async def get_cache(
    key: str,
    cache: RedisServiceDependency
):
    try:
        value = await cache.get_json(key)
        if value is None:
            raise HTTPException(
                status_code=404,
                detail="Cache key not found"
            )
        return {
            "key": key,
            "value": value
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


@router.delete("/{key}")
async def delete_cache(
    key: str,
    cache: RedisServiceDependency
):
    try:
        deleted = await cache.delete(key)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Cache key not found"
            )
        return {
            "message": "Cache deleted successfully",
            "key": key
        }
    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )
