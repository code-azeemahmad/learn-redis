import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.config.cache import (
    CATEGORY_TTL,
    NEGATIVE_CACHE_TTL,
    PRODUCT_DETAIL_TTL,
    PRODUCT_LIST_TTL,
    calculate_ttl,
)
from app.dependencies import DatabaseDependency, RedisDependency
from app.models import Product
from app.schemas import ProductCreate, ProductResponse
from app.services.redis_service import NOT_FOUND_SENTINEL, RedisService

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)

logger = logging.getLogger(__name__)


# ==========================================
# Centralized Cache Invalidation Helper
# ==========================================

async def invalidate_product_caches(
    cache: RedisService,
    product_id: int,
    category: str | None = None
) -> None:
    """
    Centralized cache invalidation for product changes.
    Invalidates individual detail, all listings, count, and category-specific caches.
    """
    keys = [
        f"v1:product:{product_id}",
        "v1:products:all",
        "v1:products:list:all",
        "v1:products:count",
    ]
    if category:
        keys.append(f"v1:products:category:{category}")

    try:
        deleted_count = await cache.delete(*keys)
        logger.info(
            "Cache invalidation SUCCESS for product %s. Keys: %s (deleted count: %s)",
            product_id,
            keys,
            deleted_count
        )
    except RedisError:
        logger.exception(
            "Cache invalidation FAILED for product %s with keys: %s",
            product_id,
            keys
        )


# ==========================================
# Product Listing Caching (GET /products)
# ==========================================

@router.get("/", response_model=list[ProductResponse])
async def get_products(
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency,
    category: str | None = None
):
    if category:
        cache_key = f"v1:products:category:{category}"
        base_ttl = CATEGORY_TTL
    else:
        cache_key = "v1:products:all"
        base_ttl = PRODUCT_LIST_TTL

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
    query = select(Product)
    if category:
        query = query.where(Product.category == category)
    result = await db.execute(query)
    products = result.scalars().all()

    # STEP 3: Convert products to JSON-compatible data
    products_data = [
        ProductResponse.model_validate(product).model_dump(mode="json")
        for product in products
    ]

    # STEP 4: Store in Redis with jittered TTL to prevent cache stampedes
    effective_ttl = calculate_ttl(base_ttl)
    try:
        await cache.set_json(cache_key, products_data, ttl=effective_ttl)
        logger.info("Stored listing %s with jittered TTL: %d s", cache_key, effective_ttl)
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

    # Invalidate affected caches via centralized helper
    await invalidate_product_caches(cache, product.id, category=product.category)

    return product


# ==========================================
# Cache-Aside: Product Detail (GET /products/{product_id})
# ==========================================

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency
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
        # Negative Caching: cache non-existent record for NEGATIVE_CACHE_TTL
        try:
            await cache.set_not_found(cache_key, ttl=NEGATIVE_CACHE_TTL)
            logger.info("Negative cached %s with TTL: %d s", cache_key, NEGATIVE_CACHE_TTL)
        except RedisError:
            logger.warning("Negative cache write failed for %s", cache_key)

        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # Step 3: Convert database object to Pydantic model
    product_response = ProductResponse.model_validate(product)

    # Step 4: Store in Redis with jittered TTL (prevent thundering herd)
    effective_ttl = calculate_ttl(PRODUCT_DETAIL_TTL)
    try:
        await cache.set_model(cache_key, product_response, ttl=effective_ttl)
        logger.info("Stored %s in cache with jittered TTL: %d s", cache_key, effective_ttl)
    except RedisError:
        logger.warning("Could not populate Redis cache for %s", cache_key)

    # Step 5: Return product
    return product_response


# ==========================================
# Invalidation on Update (PUT /products/{product_id})
# ==========================================

@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: int,
    product_data: ProductCreate,
    cache: RedisDependency,
    db: DatabaseDependency
):
    # 1. Find product in PostgreSQL
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    old_category = product.category
    product.name = product_data.name
    product.price = product_data.price
    product.category = product_data.category

    # 2. Commit to PostgreSQL (source of truth first)
    await db.commit()
    await db.refresh(product)

    product_response = ProductResponse.model_validate(product)

    # 3. Invalidate affected caches via centralized helper
    await invalidate_product_caches(cache, product.id, category=product.category)
    if old_category != product.category:
        await invalidate_product_caches(cache, product.id, category=old_category)

    # 4. Write-Through refresh with jittered TTL
    cache_key = f"v1:product:{product_id}"
    effective_ttl = calculate_ttl(PRODUCT_DETAIL_TTL)
    try:
        await cache.set_model(cache_key, product_response, ttl=effective_ttl)
        logger.info("Write-Through refreshed %s with jittered TTL: %d s", cache_key, effective_ttl)
    except RedisError:
        logger.warning("Write-Through cache refresh failed for %s", cache_key)

    # 5. Return updated product
    return product_response


# ==========================================
# Invalidation on Delete (DELETE /products/{product_id})
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

    category = product.category
    await db.delete(product)
    await db.commit()

    # Invalidate affected caches
    await invalidate_product_caches(cache, product_id, category=category)

    return {
        "message": "Product deleted successfully",
        "product_id": product_id
    }
