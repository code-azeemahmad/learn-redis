import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.openapi.docs import (
    get_swagger_ui_html,
    get_swagger_ui_oauth2_redirect_html,
)
from fastapi.responses import HTMLResponse

from app.database import AsyncSessionLocal, Base, engine
from app.routers.cache import router as cache_router
from app.routers.products import router as products_router
from app.services.cache_warming import warm_featured_products
from app.services.redis_service import RedisService
from app.swagger_dark import DARK_CSS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

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
    logger.info("Database tables initialized successfully")

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
        logger.info("Redis connected successfully")
        app.state.redis = redis_client

        # ==========================================
        # Cache Warming during Application Startup
        # ==========================================
        async with AsyncSessionLocal() as db:
            cache = RedisService(redis_client)
            await warm_featured_products(db, cache)

        yield
    finally:
        await redis_client.aclose()
        logger.info("Redis connection closed")
        await engine.dispose()
        logger.info("Database connections disposed")


# Disable default docs_url so our custom dark_swagger_ui takes precedence at /docs
app = FastAPI(
    title="Production Redis & PostgreSQL API",
    lifespan=lifespan,
    docs_url=None
)

# Register routers
app.include_router(cache_router)
app.include_router(products_router)


@app.get("/docs", include_in_schema=False)
async def dark_swagger_ui():
    html = get_swagger_ui_html(
        openapi_url=app.openapi_url or "/openapi.json",
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_ui_parameters={
            "syntaxHighlight.theme": "monokai",  # dark JSON highlighting
            "displayRequestDuration": True,      # shows response time per request
            "persistAuthorization": True,
        },
    )
    body = html.body.decode("utf-8").replace("</head>", f"<style>{DARK_CSS}</style></head>")
    return HTMLResponse(body)


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
async def swagger_ui_redirect():
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/")
async def root():
    return {"message": "Welcome to Production Redis & PostgreSQL API"}


@app.get("/health")
async def health():
    return {"status": "ok"}
