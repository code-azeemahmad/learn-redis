import os
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI

from app.database import Base, engine
from app.routers.cache import router as cache_router
from app.routers.products import router as products_router

load_dotenv()
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure PostgreSQL database tables are created
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables initialized successfully")

    # Initialize shared Redis connection pool
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
        await engine.dispose()
        print("Database connections disposed")


app = FastAPI(
    title="Production Redis & PostgreSQL API",
    lifespan=lifespan
)

# Register routers
app.include_router(cache_router)
app.include_router(products_router)


@app.get("/")
async def root():
    return {"message": "Welcome to Production Redis & PostgreSQL API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
