import json
from typing import Any
from redis.asyncio import Redis


class RedisService:
    def __init__(self, client: Redis):
        self.client = client

    async def set_json(
        self,
        key: str,
        value: Any,
        ttl: int = 300
    ) -> None:
        serialized_value = json.dumps(value)
        await self.client.set(
            key,
            serialized_value,
            ex=ttl
        )

    async def get_json(self, key: str) -> Any | None:
        cached_value = await self.client.get(key)
        if cached_value is None:
            return None
        return json.loads(cached_value)

    async def delete(self, key: str) -> bool:
        deleted = await self.client.delete(key)
        return deleted > 0

    async def ping(self) -> bool:
        return await self.client.ping()

    async def exists(self, key: str) -> bool:
        exists_count = await self.client.exists(key)
        return exists_count > 0
