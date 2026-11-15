import logging
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.dependencies import (
    CurrentSession,
    DatabaseDependency,
    SessionDependency,
)
from app.models import User
from app.schemas import (
    LoginRequest,
    SessionProfileResponse,
    UserCreate,
    UserResponse,
)
from app.utils.security import hash_password, verify_password

router = APIRouter(
    prefix="/auth",
    tags=["Authentication & Sessions"]
)

logger = logging.getLogger(__name__)

# Secure cookie flag: False for local HTTP dev, True in production
IS_SECURE_COOKIE = os.getenv("ENVIRONMENT", "development").lower() == "production"
SESSION_COOKIE_NAME = "session_id"
SESSION_COOKIE_MAX_AGE = 1800  # 30 minutes


# ==========================================
# User Registration (POST /auth/register)
# ==========================================

@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserResponse)
async def register(
    payload: UserCreate,
    db: DatabaseDependency
):
    # Check if user already exists
    normalized_email = payload.email.strip().lower()
    existing = await db.execute(
        select(User).where(User.email == normalized_email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists"
        )

    pwd = payload.password or "Password123!"
    hashed_pwd = hash_password(pwd)

    user = User(
        tenant_id=payload.tenant_id.strip().lower(),
        username=payload.username.strip(),
        email=normalized_email,
        full_name=payload.full_name.strip(),
        password_hash=hashed_pwd,
        role=payload.role or "user"
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ==========================================
# User Login (POST /auth/login)
# ==========================================

@router.post("/login")
async def login(
    payload: LoginRequest,
    response: Response,
    db: DatabaseDependency,
    session_service: SessionDependency
):
    normalized_email = payload.email.strip().lower()

    # 1. Find user in PostgreSQL
    result = await db.execute(
        select(User).where(User.email == normalized_email)
    )
    user = result.scalar_one_or_none()

    # 2. Verify credentials
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )

    # 3. Create server-side session in Redis
    try:
        session_id = await session_service.create_session(
            user_id=user.id,
            role=user.role or "user",
            tenant_id=user.tenant_id,
            ttl=SESSION_COOKIE_MAX_AGE
        )
    except RedisError:
        logger.exception("Failed to write session to Redis")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service temporarily unavailable"
        )

    # 4. Set HttpOnly session cookie
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=IS_SECURE_COOKIE,
        samesite="lax",
        max_age=SESSION_COOKIE_MAX_AGE,
        path="/"
    )

    logger.info("Session created for user %s (%s)", user.id, user.email)
    return {
        "message": "Login successful",
        "user_id": user.id,
        "role": user.role,
        "tenant_id": user.tenant_id
    }


# ==========================================
# Protected Profile (GET /auth/profile)
# ==========================================

@router.get("/profile", response_model=SessionProfileResponse)
async def get_profile(session: CurrentSession):
    """
    Protected endpoint requiring a valid Redis session cookie.
    Fails closed with HTTP 503 if Redis is unreachable.
    """
    return {
        "message": "Authenticated successfully",
        "user_id": session["user_id"],
        "role": session["role"],
        "tenant_id": session["tenant_id"],
        "created_at": session["created_at"]
    }


# ==========================================
# User Logout (POST /auth/logout)
# ==========================================

@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    session_service: SessionDependency
):
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        try:
            await session_service.delete_session(session_id)
            logger.info("Session deleted from Redis")
        except RedisError:
            logger.warning("Failed to delete session from Redis during logout")

    # Clear browser cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=IS_SECURE_COOKIE,
        samesite="lax"
    )

    return {"message": "Logout successful"}


# ==========================================
# Logout All Devices (POST /auth/logout-all)
# ==========================================

@router.post("/logout-all")
async def logout_all(
    response: Response,
    session: CurrentSession,
    session_service: SessionDependency
):
    user_id = session["user_id"]
    try:
        deleted_count = await session_service.delete_all_user_sessions(user_id)
        logger.info("Revoked %d sessions for user %s", deleted_count, user_id)
    except RedisError:
        logger.warning("Failed to delete all sessions from Redis")

    # Clear current cookie
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=IS_SECURE_COOKIE,
        samesite="lax"
    )

    return {
        "message": "All active sessions revoked across all devices",
        "user_id": user_id
    }
