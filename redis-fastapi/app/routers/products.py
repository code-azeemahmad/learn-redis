import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import DatabaseDependency, RedisDependency, get_redis_service
from app.models import Product
from app.schemas import ProductCreate, ProductResponse
from app.services.redis_service import NOT_FOUND_SENTINEL, RedisService

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

logger = logging.getLogger(__name__)


# ==========================================
# Product Listing Caching (GET /products)
# ==========================================

@router.get("/", response_model=list[ProductResponse])
async def get_products(
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency
):
    cache_key = "v1:products:all"

    # STEP 1: Check Redis
    try:
        cached_products = await cache.get_json(cache_key)
        if cached_products is not None:
            logger.info("Product list Cache HIT: %s", cache_key)
            response.headers["X-Cache"] = "HIT"
            return cached_products
    except (RedisError, ValueError):
        logger.warning("Redis cache read failed for %s", cache_key, exc_info=True)

    # STEP 2: Cache miss - query PostgreSQL
    logger.info("Product list Cache MISS: %s", cache_key)
    response.headers["X-Cache"] = "MISS"
    result = await db.execute(select(Product))
    products = result.scalars().all()

    # STEP 3: Convert products to JSON-compatible data
    products_data = [
        ProductResponse.model_validate(product).model_dump(mode="json")
        for product in products
    ]

    # STEP 4: Store the result in Redis (TTL = 120 seconds)
    try:
        await cache.set_json(cache_key, products_data, ttl=120)
    except RedisError:
        logger.warning("Could not cache product listing for %s", cache_key)

    return products_data


# ==========================================
# Create Product (POST /products)
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ProductResponse)
async def create_product(
    payload: ProductCreate,
    cache: RedisDependency,
    db: DatabaseDependency
):
    product = Product(
        name=payload.name,
        price=payload.price,
        category=payload.category
    )
    db.add(product)
    await db.commit()
    await db.refresh(product)

    # Invalidate product listing cache and any stale negative cache
    try:
        await cache.delete("v1:products:all")
        await cache.delete(f"v1:product:{product.id}")
    except RedisError:
        logger.warning("Cache invalidation failed on product creation")

    return product


# ==========================================
# Cache-Aside: Product Detail (GET /products/{product_id})
# ==========================================

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    response: Response,
    db: AsyncSession = Depends(get_db),
    cache: RedisService = Depends(get_redis_service)
):
    cache_key = f"v1:product:{product_id}"

    # Step 1: Check Redis (Cache Hit / Negative Cache Hit)
    try:
        raw_val = await cache.get_raw(cache_key)

        # Check negative cache marker
        if raw_val == NOT_FOUND_SENTINEL:
            logger.info("Cache HIT (Negative): %s", cache_key)
            response.headers["X-Cache"] = "HIT-NEGATIVE"
            raise HTTPException(
                status_code=404,
                detail="Product not found"
            )

        if raw_val is not None:
            try:
                cached_product = ProductResponse.model_validate_json(raw_val)
                logger.info("Cache HIT: %s", cache_key)
                response.headers["X-Cache"] = "HIT"
                return cached_product
            except (ValueError, Exception):
                logger.warning(
                    "Corrupted cache entry for %s, evicting",
                    cache_key,
                    exc_info=True
                )
                await cache.delete(cache_key)

    except HTTPException:
        # Re-raise explicit HTTP exceptions (e.g. 404 from negative cache)
        raise
    except (RedisError, ValueError):
        logger.warning(
            "Redis cache read failed for %s",
            cache_key,
            exc_info=True
        )

    # Step 2: Cache miss - query PostgreSQL
    logger.info("Cache MISS: %s", cache_key)
    response.headers["X-Cache"] = "MISS"

    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if product is None:
        # Negative Caching: cache non-existent record for 30s
        try:
            await cache.set_not_found(cache_key, ttl=30)
        except RedisError:
            logger.warning("Negative cache write failed for %s", cache_key)

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Step 3: Convert database object to Pydantic model
    product_response = ProductResponse.model_validate(product)

    # Step 4: Store in Redis (TTL = 300 seconds)
    try:
        await cache.set_model(cache_key, product_response, ttl=300)
    except RedisError:
        logger.warning("Could not populate Redis cache for %s", cache_key)

    # Step 5: Return product
    return product_response


# ==========================================
# Cache Invalidation on Update (PUT /products/{product_id})
# ==========================================

@router.put("/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductCreate,
    cache: RedisDependency,
    db: DatabaseDependency
):
    # Step 1: Update PostgreSQL
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    product.name = payload.name
    product.price = payload.price
    product.category = payload.category
    await db.commit()

    # Step 2: Invalidate Redis cache
    try:
        await cache.delete(f"v1:product:{product_id}")
        await cache.delete("v1:products:all")
    except RedisError:
        logger.exception("Failed to invalidate product cache for %s", product_id)

    return {
        "message": "Product updated successfully",
        "product_id": product_id
    }


# ==========================================
# Cache Invalidation on Delete (DELETE /products/{product_id})
# ==========================================

@router.delete("/{product_id}")
async def delete_product(
    product_id: int,
    cache: RedisDependency,
    db: DatabaseDependency
):
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    await db.delete(product)
    await db.commit()

    # Invalidate Redis cache
    try:
        await cache.delete(f"v1:product:{product_id}")
        await cache.delete("v1:products:all")
    except RedisError:
        logger.exception("Failed to invalidate product cache for %s", product_id)

    return {
        "message": "Product deleted successfully",
        "product_id": product_id
    }
