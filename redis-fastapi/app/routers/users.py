import logging

from fastapi import APIRouter, HTTPException, Query, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.config.cache import (
    NEGATIVE_CACHE_TTL,
    USER_PROFILE_TTL,
    calculate_ttl,
)
from app.dependencies import DatabaseDependency, RedisDependency
from app.models import User
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.services.redis_service import NOT_FOUND_SENTINEL
from app.utils.cache_keys import user_profile_cache_key

router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

logger = logging.getLogger(__name__)


# ==========================================
# Create User (POST /users)
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def create_user(
    payload: UserCreate,
    db: DatabaseDependency
):
    user = User(
        tenant_id=payload.tenant_id.strip().lower(),
        username=payload.username.strip(),
        email=payload.email.strip().lower(),
        full_name=payload.full_name.strip()
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ==========================================
# Tenant-Isolated User Profile (GET /users/{user_id}/profile)
# ==========================================

@router.get("/{user_id}/profile", response_model=UserResponse)
async def get_user_profile(
    user_id: int,
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency,
    tenant_id: str = Query(..., description="Tenant identifier (e.g. company-a)")
):
    # 1. Generate tenant-isolated cache key
    cache_key = user_profile_cache_key(tenant_id=tenant_id, user_id=user_id)

    # 2. Check Redis cache
    try:
        raw_val = await cache.get_raw(cache_key)

        # Check negative cache marker
        if raw_val == NOT_FOUND_SENTINEL:
            logger.info("User profile Cache HIT (Negative): %s", cache_key)
            response.headers["X-Cache"] = "HIT-NEGATIVE"
            raise HTTPException(
                status_code=404,
                detail="User profile not found"
            )

        if raw_val is not None:
            try:
                cached_user = UserResponse.model_validate_json(raw_val)
                logger.info("User profile Cache HIT: %s", cache_key)
                response.headers["X-Cache"] = "HIT"
                return cached_user
            except (ValueError, Exception):
                logger.warning(
                    "Corrupted cache entry for %s, evicting",
                    cache_key,
                    exc_info=True
                )
                await cache.delete(cache_key)

    except HTTPException:
        raise
    except (RedisError, ValueError):
        logger.warning("Redis cache read failed for %s", cache_key, exc_info=True)

    # 3. Cache Miss - Query PostgreSQL scoped to tenant_id
    logger.info("User profile Cache MISS: %s", cache_key)
    response.headers["X-Cache"] = "MISS"

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == tenant_id.strip().lower()
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Negative caching to protect DB from repeated misses
        try:
            await cache.set_not_found(cache_key, ttl=NEGATIVE_CACHE_TTL)
            logger.info("Negative cached %s for %d s", cache_key, NEGATIVE_CACHE_TTL)
        except RedisError:
            logger.warning("Negative cache write failed for %s", cache_key)

        raise HTTPException(
            status_code=404,
            detail="User profile not found"
        )

    user_response = UserResponse.model_validate(user)

    # 4. Store in Redis with jittered TTL
    effective_ttl = calculate_ttl(USER_PROFILE_TTL)
    try:
        await cache.set_model(cache_key, user_response, ttl=effective_ttl)
        logger.info("Stored user profile %s in cache with jittered TTL: %d s", cache_key, effective_ttl)
    except RedisError:
        logger.warning("Could not cache user profile for %s", cache_key)

    return user_response


# ==========================================
# Update User Profile (PUT /users/{user_id}/profile)
# ==========================================

@router.put("/{user_id}/profile", response_model=UserResponse)
async def update_user_profile(
    user_id: int,
    payload: UserUpdate,
    cache: RedisDependency,
    db: DatabaseDependency,
    tenant_id: str = Query(..., description="Tenant identifier")
):
    normalized_tenant = tenant_id.strip().lower()

    # 1. Fetch user from PostgreSQL
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == normalized_tenant
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    # 2. Update fields
    if payload.username is not None:
        user.username = payload.username.strip()
    if payload.email is not None:
        user.email = payload.email.strip().lower()
    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()

    # 3. Commit to PostgreSQL first (Source of truth)
    await db.commit()
    await db.refresh(user)

    user_response = UserResponse.model_validate(user)

    # 4. Invalidate old cache key
    cache_key = user_profile_cache_key(tenant_id=normalized_tenant, user_id=user_id)
    try:
        await cache.delete(cache_key)
        logger.info("Invalidated cache key %s after profile update", cache_key)
    except RedisError:
        logger.warning("Cache invalidation failed for %s", cache_key)

    return user_response


# ==========================================
# Delete User (DELETE /users/{user_id})
# ==========================================

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    cache: RedisDependency,
    db: DatabaseDependency,
    tenant_id: str = Query(..., description="Tenant identifier")
):
    normalized_tenant = tenant_id.strip().lower()

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.tenant_id == normalized_tenant
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    await db.delete(user)
    await db.commit()

    # Invalidate cache
    cache_key = user_profile_cache_key(tenant_id=normalized_tenant, user_id=user_id)
    try:
        await cache.delete(cache_key)
        logger.info("Invalidated cache key %s after user deletion", cache_key)
    except RedisError:
        logger.warning("Cache deletion failed for %s", cache_key)

    return {
        "message": "User deleted successfully",
        "user_id": user_id,
        "tenant_id": normalized_tenant
    }
