from redis.asyncio import Redis
from redis.exceptions import RedisError

FIXED_WINDOW_SCRIPT = """
local current = redis.call("INCR", KEYS[1])
if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end
local ttl = redis.call("TTL", KEYS[1])
return {current, ttl}
"""


class RateLimiter:
    def __init__(self, redis_client: Redis):
        self.redis = redis_client

    async def is_allowed(
        self,
        key: str,
        limit: int,
        window_seconds: int
    ) -> dict:
        """
        Atomically increments a fixed-window counter and returns rate-limit metadata.
        Uses a Redis Lua script to guarantee atomicity between INCR and EXPIRE.
        """
        result = await self.redis.eval(
            FIXED_WINDOW_SCRIPT,
            1,
            key,
            window_seconds
        )
        current_count = int(result[0])
        remaining_ttl = int(result[1])
        return {
            "allowed": current_count <= limit,
            "limit": limit,
            "current": current_count,
            "remaining": max(0, limit - current_count),
            "retry_after": max(0, remaining_ttl),
        }
