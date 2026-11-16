import json
import logging
from datetime import datetime, timezone
from typing import Any
import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import LLMQuery
from app.services.embedding_service import EmbeddingService
from app.services.qdrant_service import QdrantService
from app.utils.cache_keys import generate_llm_cache_key

logger = logging.getLogger(__name__)


class LLMService:
    def __init__(
        self,
        redis: Redis,
        qdrant_service: QdrantService,
        embedding_service: EmbeddingService,
        ollama_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        cache_ttl: int = settings.LLM_CACHE_TTL,
        similarity_threshold: float = settings.SIMILARITY_THRESHOLD
    ):
        self.redis = redis
        self.qdrant = qdrant_service
        self.embeddings = embedding_service
        self.ollama_url = ollama_url
        self.model = model
        self.cache_ttl = cache_ttl
        self.similarity_threshold = similarity_threshold

    async def generate_response(
        self,
        prompt: str,
        db: AsyncSession,
        system_prompt: str = "You are a helpful assistant.",
        temperature: float = 0.2,
        threshold: float | None = None
    ) -> dict[str, Any]:
        """
        Coordinates the 3-layer architecture from db.md:
        1. Layer 1: Redis Exact Match Cache (fast, sub-millisecond)
        2. Layer 2: Qdrant Semantic Cache (vector similarity on embeddings)
        3. Layer 3: Ollama Inference -> Persist to PostgreSQL (Source of truth)
                    -> Upsert to Qdrant -> Cache in Redis
        """
        active_threshold = threshold if threshold is not None else self.similarity_threshold

        # ============================================================
        # 1. LAYER 1: Redis Exact Cache Lookup
        # ============================================================
        exact_key = generate_llm_cache_key(
            prompt=prompt,
            model=self.model,
            system_prompt=system_prompt,
            temperature=temperature
        )

        try:
            cached_exact = await self.redis.get(exact_key)
            if cached_exact is not None:
                logger.info("L1 EXACT CACHE HIT in Redis: %s", exact_key)
                data = json.loads(cached_exact)
                return {
                    "model": self.model,
                    "response": data.get("response", ""),
                    "source": "redis_exact_cache",
                    "cache_key": exact_key,
                    "similarity": 1.0,
                    "matched_prompt": data.get("prompt", prompt),
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "temperature": temperature
                }
        except (RedisError, ValueError, Exception) as err:
            logger.warning("Redis L1 read failed for %s: %s", exact_key, err)

        # ============================================================
        # 2. LAYER 2: Qdrant Semantic Vector Search
        # ============================================================
        query_vector = None
        try:
            logger.info("Generating embedding for semantic search with '%s'...", self.embeddings.model)
            query_vector = await self.embeddings.get_embedding(prompt)

            semantic_match = await self.qdrant.search_similar(
                vector=query_vector,
                threshold=active_threshold
            )

            if semantic_match is not None:
                score = round(float(semantic_match["score"]), 4)
                payload = semantic_match.get("payload", {})
                cached_answer = payload.get("response")
                matched_prompt = payload.get("prompt", "")
                pg_id = payload.get("postgres_id")

                logger.info(
                    "L2 SEMANTIC CACHE HIT in Qdrant! Score: %s (>= %s), Matched: '%s'",
                    score, active_threshold, matched_prompt
                )

                # Record hit in PostgreSQL if record ID is known
                if pg_id:
                    try:
                        await db.execute(
                            update(LLMQuery)
                            .where(LLMQuery.id == pg_id)
                            .values(hit_count=LLMQuery.hit_count + 1)
                        )
                        await db.commit()
                    except Exception as db_err:
                        logger.warning("Failed to increment hit_count in PostgreSQL: %s", db_err)

                # Store in Redis L1 so next identical request doesn't need vector search
                try:
                    await self.redis.set(
                        exact_key,
                        json.dumps({
                            "response": cached_answer,
                            "prompt": prompt,
                            "matched_prompt": matched_prompt,
                            "model": self.model
                        }),
                        ex=self.cache_ttl
                    )
                except RedisError:
                    pass

                return {
                    "model": self.model,
                    "response": cached_answer,
                    "source": "qdrant_semantic_cache",
                    "cache_key": exact_key,
                    "similarity": score,
                    "matched_prompt": matched_prompt,
                    "prompt": prompt,
                    "system_prompt": system_prompt,
                    "temperature": temperature
                }

        except Exception as sem_err:
            logger.warning("Semantic search step failed (continuing to inference): %s", sem_err)

        # ============================================================
        # 3. LAYER 3: LLM Inference via Ollama (Cache Miss)
        # ============================================================
        logger.info("CACHE MISS - Generating completion using Ollama model '%s'", self.model)

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
            res = await client.post(
                f"{self.ollama_url}/api/chat",
                json=payload
            )
            res.raise_for_status()
            res_json = res.json()
            generated_text = res_json.get("message", {}).get("content", "")

        # ============================================================
        # 4. PERSIST TO POSTGRESQL (Durable Source of Truth)
        # ============================================================
        db_query = LLMQuery(
            prompt=prompt,
            response=generated_text,
            model=self.model,
            system_prompt=system_prompt,
            temperature=temperature,
            prompt_hash=exact_key,
            created_at=datetime.now(timezone.utc)
        )
        db.add(db_query)
        await db.commit()
        await db.refresh(db_query)
        logger.info("Persisted query record ID %d to PostgreSQL", db_query.id)

        # ============================================================
        # 5. INDEX IN QDRANT (Vector Index for Semantic Search)
        # ============================================================
        if query_vector is not None:
            try:
                point_id = await self.qdrant.upsert_point(
                    vector=query_vector,
                    payload={
                        "prompt": prompt,
                        "response": generated_text,
                        "model": self.model,
                        "postgres_id": db_query.id,
                        "created_at": db_query.created_at.isoformat()
                    }
                )
                db_query.qdrant_point_id = point_id
                await db.commit()
                logger.info("Indexed vector point %s in Qdrant", point_id)
            except Exception as q_err:
                logger.warning("Failed to index vector in Qdrant: %s", q_err)

        # ============================================================
        # 6. CACHE IN REDIS (Fast Disposable L1 Cache)
        # ============================================================
        try:
            await self.redis.set(
                exact_key,
                json.dumps({
                    "response": generated_text,
                    "prompt": prompt,
                    "model": self.model
                }),
                ex=self.cache_ttl
            )
            logger.info("Stored response in Redis L1 cache for %d s", self.cache_ttl)
        except RedisError:
            pass

        return {
            "model": self.model,
            "response": generated_text,
            "source": "ollama_inference",
            "cache_key": exact_key,
            "similarity": 0.0,
            "matched_prompt": None,
            "prompt": prompt,
            "system_prompt": system_prompt,
            "temperature": temperature
        }

    async def rebuild_qdrant_from_postgres(self, db: AsyncSession) -> int:
        """
        Rebuilds Qdrant vector index from PostgreSQL historical queries (db.md).
        Demonstrates that Qdrant is completely rebuildable from PostgreSQL source of truth.
        """
        result = await db.execute(select(LLMQuery))
        queries = result.scalars().all()
        rebuilt_count = 0

        for q in queries:
            try:
                vec = await self.embeddings.get_embedding(q.prompt)
                point_id = await self.qdrant.upsert_point(
                    vector=vec,
                    payload={
                        "prompt": q.prompt,
                        "response": q.response,
                        "model": q.model,
                        "postgres_id": q.id,
                        "created_at": q.created_at.isoformat()
                    }
                )
                q.qdrant_point_id = point_id
                rebuilt_count += 1
            except Exception as e:
                logger.error("Error rebuilding vector for query ID %d: %s", q.id, e)

        await db.commit()
        return rebuilt_count
