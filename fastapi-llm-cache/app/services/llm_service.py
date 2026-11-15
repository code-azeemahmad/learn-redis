import json
import logging
from typing import Any

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.utils.cache_keys import generate_llm_cache_key

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        redis: Redis,
        ollama_url: str,
        model: str,
        cache_ttl: int
    ):
        self.redis = redis
        self.ollama_url = ollama_url
        self.model = model
        self.cache_ttl = cache_ttl

    async def generate_response(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.2
    ) -> dict[str, Any]:
        """
        Generates an LLM completion, checking Redis cache before delegating
        to the Ollama inference server. Stores result in Redis on cache miss.
        """
        cache_key = generate_llm_cache_key(
            prompt=prompt,
            model=self.model,
            system_prompt=system_prompt,
            temperature=temperature
        )

        # 1. Check Redis Cache
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data is not None:
                logger.info("LLM Cache HIT: %s", cache_key)
                result = json.loads(cached_data)
                result["source"] = "redis"
                result["cache_key"] = cache_key
                return result
        except (RedisError, ValueError, Exception) as err:
            logger.warning("Redis cache read failed for %s: %s", cache_key, err)

        # 2. Cache Miss - Query Ollama API
        logger.info("LLM Cache MISS: %s - querying Ollama model '%s'", cache_key, self.model)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                response = await client.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload
                )
                response.raise_for_status()
                response_json = response.json()
                assistant_message = response_json.get("message", {}).get("content", "")
            except httpx.HTTPError as err:
                logger.error("Ollama API call failed: %s", err)
                raise err

        result = {
            "model": self.model,
            "response": assistant_message,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature,
            "source": "ollama",
            "cache_key": cache_key
        }

        # 3. Store response in Redis with TTL
        try:
            # Store serializable copy
            cache_payload = {
                "model": self.model,
                "response": assistant_message,
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature
            }
            await self.redis.set(
                cache_key,
                json.dumps(cache_payload),
                ex=self.cache_ttl
            )
            logger.info("Cached LLM response under key %s (TTL: %d s)", cache_key, self.cache_ttl)
        except RedisError as err:
            logger.warning("Redis cache write failed for %s: %s", cache_key, err)

        return result
