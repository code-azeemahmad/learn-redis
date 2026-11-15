import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from redis.exceptions import RedisError

from app.services.llm_service import LLMService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
LLM_CACHE_TTL = int(os.getenv("LLM_CACHE_TTL", "3600"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize shared asynchronous Redis connection pool
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    app.state.redis = redis_client
    try:
        await redis_client.ping()
        logger.info("Connected to Redis successfully at %s", REDIS_URL)
        yield
    finally:
        await redis_client.aclose()
        logger.info("Redis connection closed")


app = FastAPI(
    title="FastAPI + Redis + Ollama LLM Caching",
    description="LLM response caching service to reduce inference latency and computational costs",
    version="1.0.0",
    lifespan=lifespan
)


def get_llm_service(request: Request) -> LLMService:
    return LLMService(
        redis=request.app.state.redis,
        ollama_url=OLLAMA_BASE_URL,
        model=OLLAMA_MODEL,
        cache_ttl=LLM_CACHE_TTL
    )


LLMServiceDependency = Annotated[LLMService, Depends(get_llm_service)]


class ChatRequest(BaseModel):
    prompt: str = Field(..., description="User query / prompt for the LLM")
    system_prompt: str = Field("You are a helpful assistant.", description="System instruction prompt")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Sampling temperature")


class ChatResponse(BaseModel):
    model: str
    response: str
    source: str  # "redis" or "ollama"
    cache_key: str
    prompt: str
    system_prompt: str
    temperature: float


@app.get("/")
def root():
    return {
        "message": "FastAPI + Redis + Ollama LLM Caching API",
        "docs": "/docs",
        "model": OLLAMA_MODEL,
        "ollama_url": OLLAMA_BASE_URL,
        "cache_ttl_seconds": LLM_CACHE_TTL
    }


@app.get("/health")
async def health(request: Request):
    try:
        await request.app.state.redis.ping()
        return {"status": "ok", "redis": "connected", "model": OLLAMA_MODEL}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis connection failed: {e}"
        )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    response: Response,
    llm_service: LLMServiceDependency
):
    """
    Submits a prompt to the LLM. If an identical prompt/configuration was previously cached,
    returns the response from Redis in milliseconds. Otherwise, invokes Ollama and caches the output.
    """
    try:
        result = await llm_service.generate_response(
            prompt=payload.prompt,
            system_prompt=payload.system_prompt,
            temperature=payload.temperature
        )
        response.headers["X-Cache"] = "HIT" if result["source"] == "redis" else "MISS"
        return result
    except Exception as err:
        logger.exception("LLM generation error")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Inference error: {err}"
        )
