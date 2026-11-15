import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

DEFAULT_SESSION_TTL = 1800  # 30 minutes


class SessionService:
    def __init__(self, redis: Redis):
        self.redis = redis

    def _hash_session_id(self, session_id: str) -> str:
        """
        Hashes the session ID using SHA-256 before using it as a Redis key.
        Prevents raw session tokens from being exposed if Redis data is dumped.
        """
        return hashlib.sha256(session_id.encode("utf-8")).hexdigest()

    async def create_session(
        self,
        user_id: int,
        role: str,
        tenant_id: str = "default",
        ttl: int = DEFAULT_SESSION_TTL
    ) -> str:
        """
        Generates a cryptographically secure random session ID, stores session data
        under its SHA-256 hash in Redis, and indexes it under the user's active sessions.
        Returns the unhashed session ID for the HTTP cookie.
        """
        session_id = secrets.token_urlsafe(32)
        session_hash = self._hash_session_id(session_id)
        session_key = f"session:{session_hash}"

        session_data = {
            "user_id": user_id,
            "role": role,
            "tenant_id": tenant_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Store session with expiration
        await self.redis.set(session_key, json.dumps(session_data), ex=ttl)

        # Index session under user for multi-device tracking
        user_sessions_key = f"user:{user_id}:sessions"
        await self.redis.sadd(user_sessions_key, session_hash)
        await self.redis.expire(user_sessions_key, ttl * 2)

        return session_id

    async def get_session(
        self,
        session_id: str,
        slide: bool = False,
        sliding_ttl: int = DEFAULT_SESSION_TTL
    ) -> dict[str, Any] | None:
        """
        Retrieves session data by hashing the provided session ID.
        Supports optional sliding expiration to extend active sessions.
        """
        if not session_id:
            return None

        session_hash = self._hash_session_id(session_id)
        session_key = f"session:{session_hash}"

        cached_data = await self.redis.get(session_key)
        if cached_data is None:
            return None

        # Extend session lifetime if sliding expiration is requested
        if slide:
            await self.redis.expire(session_key, sliding_ttl)

        return json.loads(cached_data)

    async def delete_session(self, session_id: str) -> bool:
        """
        Deletes the session from Redis and cleans up user device index.
        """
        if not session_id:
            return False

        session_hash = self._hash_session_id(session_id)
        session_key = f"session:{session_hash}"

        data = await self.redis.get(session_key)
        if data:
            try:
                parsed = json.loads(data)
                user_id = parsed.get("user_id")
                if user_id:
                    await self.redis.srem(f"user:{user_id}:sessions", session_hash)
            except Exception:
                pass

        deleted = await self.redis.delete(session_key)
        return deleted > 0

    async def delete_all_user_sessions(self, user_id: int) -> int:
        """
        Revokes all active sessions for a user across all devices.
        """
        user_sessions_key = f"user:{user_id}:sessions"
        session_hashes = await self.redis.smembers(user_sessions_key)
        deleted_count = 0
        if session_hashes:
            keys = [f"session:{sh}" for sh in session_hashes]
            deleted_count = await self.redis.delete(*keys)
        await self.redis.delete(user_sessions_key)
        return deleted_count
