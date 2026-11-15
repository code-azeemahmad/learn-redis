import json
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError
from redis.asyncio import Redis

ModelT = TypeVar("ModelT", bound=BaseModel)

NOT_FOUND_SENTINEL = "__NOT_FOUND__"


class RedisService:
    def __init__(self, client: Redis):
        self.client = client

    # Retrieve raw string directly
    async def get_raw(self, key: str) -> str | None:
        return await self.client.get(key)

    # Store ordinary Python data as JSON
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

    # Retrieve ordinary JSON data
    async def get_json(self, key: str) -> Any | None:
        cached_value = await self.client.get(key)
        if cached_value is None:
            return None
        return json.loads(cached_value)

    # Store a Pydantic model directly as JSON
    async def set_model(
        self,
        key: str,
        value: BaseModel,
        ttl: int = 300
    ) -> None:
        serialized_value = value.model_dump_json()
        await self.client.set(
            key,
            serialized_value,
            ex=ttl
        )

    # Retrieve and validate a Pydantic model directly from JSON
    async def get_model(
        self,
        key: str,
        model_class: type[ModelT],
        ignore_corrupted: bool = False
    ) -> ModelT | None:
        cached_value = await self.client.get(key)
        if cached_value is None:
            return None
        if cached_value == NOT_FOUND_SENTINEL:
            return None
        try:
            return model_class.model_validate_json(cached_value)
        except (ValidationError, ValueError) as err:
            if ignore_corrupted:
                # Invalidate corrupted cache entry and treat as cache miss
                await self.client.delete(key)
                return None
            raise err

    # Negative caching methods
    async def set_not_found(self, key: str, ttl: int = 30) -> None:
        await self.client.set(key, NOT_FOUND_SENTINEL, ex=ttl)

    async def is_not_found(self, key: str) -> bool:
        val = await self.client.get(key)
        return val == NOT_FOUND_SENTINEL

    # Multi-key deletion and management
    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        return await self.client.delete(*keys)

    async def ping(self) -> bool:
        return await self.client.ping()

    async def exists(self, key: str) -> bool:
        exists_count = await self.client.exists(key)
        return exists_count > 0
