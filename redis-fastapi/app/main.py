import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI

from app.routers.cache import router as cache_router

load_dotenv()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        max_connections=15,
        socket_connect_timeout=3,
        socket_timeout=5,
        health_check_interval=30
    )

    try:
        await redis_client.ping()
        print("Redis connected successfully")
        app.state.redis = redis_client
        yield
    finally:
        await redis_client.aclose()
        print("Redis connection closed")


app = FastAPI(
    title="Production Redis API",
    lifespan=lifespan
)

app.include_router(cache_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Production Redis API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
