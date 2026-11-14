
import json
import os
from contextlib import asynccontextmanager

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from redis.exceptions import RedisError

# Load environment variables from .env
load_dotenv()

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0"
)


# Manage the Redis connection during application startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):   # Create one Redis client per application process, reuse it across requests, and close it during shutdown.
    client = redis.from_url(
        REDIS_URL,
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )

    try:
        await client.ping()
        print("Redis connected successfully")

        app.state.redis = client

        yield

    finally:
        await client.aclose()
        print("Redis connection closed")


# Create FastAPI application
app = FastAPI(
    title="FastAPI Redis Integration",
    lifespan=lifespan
)

# workers ≈ number of CPU cores

@app.get("/cache/{key}")
async def get_cache(key: str, request: Request):

    redis_client = request.app.state.redis

    try:
        value = await redis_client.get(key)

        return {
            "key": key,
            "value": value
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


@app.post("/cache/{key}")
async def set_cache(key: str, request: Request):

    redis_client = request.app.state.redis

    try:
        await redis_client.set(
            key,
            "Hello from FastAPI",
            ex=300
        )

        return {
            "message": "Value cached successfully"
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )

# Product request model
class Product(BaseModel):
    name: str
    price: float
    category: str


# Health endpoint
@app.get("/")
async def home():
    return {"hello": "world"}

# Health endpoint
@app.get("/health")
async def health():
    return {"status": "ok"}


# Store a product in Redis
@app.post("/products/{product_id}")
async def create_product(
    product_id: int,
    product: Product,
    request: Request
):
    client = request.app.state.redis

    try:
        product_data = product.model_dump()

        await client.set(
            f"product:{product_id}",
            json.dumps(product_data),
            ex=300
        )

        return {
            "message": "Product stored successfully",
            "product_id": product_id,
            "ttl": 300
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


# Retrieve a product from Redis
@app.get("/products/{product_id}")
async def get_product(
    product_id: int,
    request: Request
):
    client = request.app.state.redis

    try:
        cached_product = await client.get(
            f"product:{product_id}"
        )

        if cached_product is None:
            raise HTTPException(
                status_code=404,
                detail="Product not found in Redis"
            )

        return {
            "product_id": product_id,
            "product": json.loads(cached_product)
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )


# Delete a product from Redis
@app.delete("/products/{product_id}")
async def delete_product(
    product_id: int,
    request: Request
):
    client = request.app.state.redis

    try:
        deleted = await client.delete(
            f"product:{product_id}"
        )

        if deleted == 0:
            raise HTTPException(
                status_code=404,
                detail="Product not found in Redis"
            )

        return {
            "message": "Product deleted successfully",
            "product_id": product_id
        }

    except RedisError:
        raise HTTPException(
            status_code=503,
            detail="Redis is temporarily unavailable"
        )
