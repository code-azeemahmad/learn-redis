import logging
from contextlib import asynccontextmanager
from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import mask_connection_url, settings
from app.database import AsyncSessionLocal, Base, engine, get_db
from app.models import LLMQuery
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService
from app.services.qdrant_service import QdrantService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Validate required environment settings (e.g. POSTGRES_URL)
    settings.validate()

    # 1. PostgreSQL: Ensure tables are created (Source of truth)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("PostgreSQL database tables initialized successfully")

    # 2. Redis: Initialize shared asynchronous connection pool
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    await redis_client.ping()
    logger.info("Connected to Redis successfully at %s", mask_connection_url(settings.REDIS_URL))
    app.state.redis = redis_client

    # 3. Qdrant: Initialize and ensure vector collection exists
    qdrant_service = QdrantService(qdrant_url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)
    await qdrant_service.ensure_collection(
        collection_name=settings.COLLECTION_NAME,
        vector_size=settings.EMBEDDING_DIM
    )
    app.state.qdrant = qdrant_service

    # 4. Ollama Embeddings Service
    embedding_service = EmbeddingService(
        ollama_url=settings.OLLAMA_BASE_URL,
        model=settings.EMBEDDING_MODEL
    )
    app.state.embeddings = embedding_service

    yield

    await redis_client.aclose()
    await engine.dispose()
    logger.info("Connections closed on shutdown")


app = FastAPI(
    title="FastAPI + Redis + Qdrant + PostgreSQL Semantic Caching",
    description="Multi-tier semantic cache architecture for AI applications: Redis L1 (exact match), Qdrant L2 (vector similarity), and PostgreSQL (durable source of truth).",
    version="2.0.0",
    lifespan=lifespan
)


def get_llm_service(request: Request) -> LLMService:
    return LLMService(
        redis=request.app.state.redis,
        qdrant_service=request.app.state.qdrant,
        embedding_service=request.app.state.embeddings,
        ollama_url=settings.OLLAMA_BASE_URL,
        model=settings.OLLAMA_MODEL,
        cache_ttl=settings.LLM_CACHE_TTL,
        similarity_threshold=settings.SIMILARITY_THRESHOLD
    )


LLMServiceDependency = Annotated[LLMService, Depends(get_llm_service)]
DatabaseDependency = Annotated[AsyncSession, Depends(get_db)]


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User query / prompt for the LLM")
    system_prompt: str = Field("You are a helpful assistant.", description="System instruction prompt")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")
    similarity_threshold: float = Field(
        settings.SIMILARITY_THRESHOLD,
        ge=0.5,
        le=1.0,
        description=f"Cosine similarity cutoff for semantic match (default {settings.SIMILARITY_THRESHOLD})"
    )


class ChatResponse(BaseModel):
    model: str
    response: str
    source: str  # "redis_exact_cache", "qdrant_semantic_cache", or "ollama_inference"
    similarity: float
    matched_prompt: str | None = None
    cache_key: str
    prompt: str
    system_prompt: str
    temperature: float


@app.get("/")
def root():
    return {
        "message": "FastAPI + Redis + Qdrant + PostgreSQL Semantic Caching API",
        "docs": "/docs",
        "models": {
            "llm": settings.OLLAMA_MODEL,
            "embeddings": settings.EMBEDDING_MODEL
        },
        "services": {
            "redis": mask_connection_url(settings.REDIS_URL),
            "qdrant": mask_connection_url(settings.QDRANT_URL),
            "postgres": mask_connection_url(settings.POSTGRES_URL)
        },
        "semantic_threshold": settings.SIMILARITY_THRESHOLD,
        "cache_ttl": settings.LLM_CACHE_TTL
    }


@app.get("/health")
async def health(request: Request, db: DatabaseDependency):
    status_info = {
        "status": "ok",
        "redis": "connected",
        "qdrant": "connected",
        "postgres": "connected",
        "llm_model": settings.OLLAMA_MODEL,
        "embedding_model": settings.EMBEDDING_MODEL
    }

    # Verify Redis
    try:
        await request.app.state.redis.ping()
    except Exception as e:
        status_info["redis"] = f"error: {e}"
        status_info["status"] = "degraded"

    # Verify PostgreSQL
    try:
        await db.execute(select(1))
    except Exception as e:
        status_info["postgres"] = f"error: {e}"
        status_info["status"] = "degraded"

    # Verify Qdrant
    try:
        count = await request.app.state.qdrant.count_points(settings.COLLECTION_NAME)
        status_info["qdrant_vectors"] = count
    except Exception as e:
        status_info["qdrant"] = f"error: {e}"
        status_info["status"] = "degraded"

    return status_info


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    response: Response,
    db: DatabaseDependency,
    llm_service: LLMServiceDependency
):
    """
    Submits a query to the LLM semantic cache system:
    1. Check Redis L1 Exact Match Cache.
    2. If miss, compute embedding and search Qdrant L2 Semantic Cache.
    3. If miss, generate completion with Ollama, persist to PostgreSQL, index in Qdrant, and cache in Redis.
    """
    try:
        result = await llm_service.generate_response(
            prompt=payload.prompt,
            db=db,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature,
            threshold=payload.similarity_threshold
        )

        if result["source"] == "redis_exact_cache":
            response.headers["X-Cache"] = "HIT-EXACT"
        elif result["source"] == "qdrant_semantic_cache":
            response.headers["X-Cache"] = "HIT-SEMANTIC"
        else:
            response.headers["X-Cache"] = "MISS"

        return result
    except Exception as err:
        logger.exception("Chat generation failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Inference error: {err}"
        )


@app.get("/cache/stats")
async def cache_stats(request: Request, db: DatabaseDependency):
    """
    Returns metrics across all 3 storage tiers.
    """
    # PostgreSQL queries count
    res = await db.execute(select(func.count(LLMQuery.id)))
    pg_count = res.scalar_one()

    # Qdrant indexed vector count
    qdrant_count = await request.app.state.qdrant.count_points(settings.COLLECTION_NAME)

    # Redis cached keys count
    redis_keys = await request.app.state.redis.keys("v1:llm:*")

    return {
        "postgresql_source_of_truth_records": pg_count,
        "qdrant_indexed_vectors": qdrant_count,
        "redis_l1_cached_keys": len(redis_keys),
        "cached_redis_keys": redis_keys
    }


@app.post("/cache/rebuild")
async def rebuild_cache(db: DatabaseDependency, llm_service: LLMServiceDependency):
    """
    Rebuilds the Qdrant vector index from the PostgreSQL source of truth (db.md).
    Proves that the vector index is completely rebuildable from PostgreSQL records.
    """
    rebuilt_count = await llm_service.rebuild_qdrant_from_postgres(db=db)
    return {
        "message": "Qdrant vector index rebuild complete",
        "vectors_rebuilt": rebuilt_count
    }
