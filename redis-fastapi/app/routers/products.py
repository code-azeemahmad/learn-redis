from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from redis.exceptions import RedisError
from sqlalchemy import select

from app.dependencies import DatabaseDependency, RedisDependency
from app.models import Product
from app.schemas import ProductCreate, ProductResponse

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


# ==========================================
# Task 2: Product Listing Caching (GET /products)
# ==========================================

@router.get("/", response_model=list[ProductResponse])
async def get_products(
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency
):
    cache_key = "products:all"

    # STEP 1: Check Redis
    try:
        cached_products = await cache.get_json(cache_key)
        if cached_products is not None:
            print("PRODUCT LIST CACHE HIT")
            response.headers["X-Cache"] = "HIT"
            return cached_products
    except RedisError:
        print("Redis unavailable. Querying PostgreSQL.")

    # STEP 2: Query PostgreSQL
    print("PRODUCT LIST CACHE MISS")
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
        print("Could not cache product listing.")

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

    # Invalidate product listing cache
    try:
        await cache.delete("products:all")
    except RedisError:
        print("Cache invalidation failed for products listing.")

    return product


# ==========================================
# Task 1: Product Detail Caching (GET /products/{product_id})
# ==========================================

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency
):
    cache_key = f"product:{product_id}"

    # STEP 1: Check Redis
    try:
        cached_product = await cache.get_json(cache_key)
        if cached_product is not None:
            print("CACHE HIT")
            response.headers["X-Cache"] = "HIT"
            return cached_product
    except RedisError:
        print("Redis unavailable. Continuing with PostgreSQL.")

    # STEP 2: Cache miss - query PostgreSQL
    print("CACHE MISS")
    response.headers["X-Cache"] = "MISS"
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if product is None:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    # STEP 3: Convert database model to response data
    product_data = ProductResponse.model_validate(product).model_dump(mode="json")

    # STEP 4: Store in Redis (TTL = 300 seconds)
    try:
        await cache.set_json(cache_key, product_data, ttl=300)
    except RedisError:
        print("Could not populate Redis cache.")

    # STEP 5: Return the product
    return product_data


# ==========================================
# Task 3: Cache Invalidation on Update (PUT /products/{product_id})
# ==========================================

@router.put("/{product_id}")
async def update_product(
    product_id: int,
    payload: ProductCreate,
    cache: RedisDependency,
    db: DatabaseDependency
):
    # STEP 1: Update PostgreSQL
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

    # STEP 2: Invalidate Redis cache
    try:
        await cache.delete(f"product:{product_id}")
        await cache.delete("products:all")
    except RedisError:
        print("Cache invalidation failed.")

    return {
        "message": "Product updated successfully",
        "product_id": product_id
    }


# ==========================================
# Delete Product & Invalidate Cache (DELETE /products/{product_id})
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
        await cache.delete(f"product:{product_id}")
        await cache.delete("products:all")
    except RedisError:
        print("Cache invalidation failed.")

    return {
        "message": "Product deleted successfully",
        "product_id": product_id
    }
