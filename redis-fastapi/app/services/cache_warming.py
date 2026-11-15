import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Product
from app.schemas import ProductResponse
from app.services.redis_service import RedisService
from app.utils.cache_utils import get_cache_ttl

logger = logging.getLogger(__name__)

FEATURED_PRODUCTS_CACHE_KEY = "v1:products:featured"
FEATURED_PRODUCTS_TTL = 300  # 5 minutes


async def warm_featured_products(
    db: AsyncSession,
    cache: RedisService
) -> int:
    """
    Preloads featured products into Redis cache during application startup or background job.
    Uses get_cache_ttl() to apply random jitter to prevent cache stampedes.
    """
    logger.info("Starting cache warming for featured products...")
    try:
        # Fetch featured products from PostgreSQL
        result = await db.execute(
            select(Product)
            .where(Product.is_featured == True)
            .limit(20)
        )
        products = result.scalars().all()

        # Convert database objects into Pydantic models
        product_responses = [
            ProductResponse.model_validate(product)
            for product in products
        ]

        # Calculate jittered TTL using get_cache_ttl
        effective_ttl = get_cache_ttl(FEATURED_PRODUCTS_TTL, jitter=60)

        # Store the result in Redis
        payload = [
            product.model_dump(mode="json")
            for product in product_responses
        ]
        await cache.set_json(
            FEATURED_PRODUCTS_CACHE_KEY,
            payload,
            ttl=effective_ttl
        )

        logger.info(
            "Cache warming complete: %d featured products cached at '%s' (Jittered TTL: %d s)",
            len(products),
            FEATURED_PRODUCTS_CACHE_KEY,
            effective_ttl
        )
        return len(products)
    except Exception as e:
        logger.warning(
            "Cache warming failed: %s. Application will continue without pre-warmed cache.",
            e,
            exc_info=True
        )
        return 0
