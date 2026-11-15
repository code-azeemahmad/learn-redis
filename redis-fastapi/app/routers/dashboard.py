import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status
from redis.exceptions import RedisError
from sqlalchemy import func, select

from app.config.cache import DASHBOARD_TTL, calculate_ttl
from app.dependencies import DatabaseDependency, RedisDependency
from app.models import Order
from app.schemas import DashboardStatsResponse, OrderCreate, OrderResponse
from app.utils.cache_keys import dashboard_stats_cache_key

router = APIRouter(
    prefix="/dashboard",
    tags=["Dashboard"]
)

logger = logging.getLogger(__name__)


# ==========================================
# Dashboard Statistics (GET /dashboard/stats)
# ==========================================

@router.get("/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats(
    tenant_id: str,
    start_date: datetime,
    end_date: datetime,
    response: Response,
    cache: RedisDependency,
    db: DatabaseDependency
):
    if start_date >= end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date must be before end_date"
        )

    # 1. Generate normalized cache key
    cache_key = dashboard_stats_cache_key(
        tenant_id=tenant_id,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat()
    )

    # 2. Check Redis cache first
    try:
        cached_stats = await cache.get_json(cache_key)
        if cached_stats is not None:
            logger.info("Dashboard stats Cache HIT: %s", cache_key)
            response.headers["X-Cache"] = "HIT"
            return {
                "source": "redis",
                "stats": cached_stats
            }
    except (RedisError, ValueError):
        logger.warning("Redis cache read failed for %s", cache_key, exc_info=True)

    # 3. Cache Miss - Execute aggregation query in PostgreSQL
    logger.info("Dashboard stats Cache MISS: %s", cache_key)
    response.headers["X-Cache"] = "MISS"

    query = (
        select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.avg(Order.total_amount), 0)
        )
        .where(
            Order.tenant_id == tenant_id.strip().lower(),
            Order.created_at >= start_date,
            Order.created_at <= end_date,
            Order.status == "completed"
        )
    )

    result = await db.execute(query)
    total_orders, total_revenue, avg_order_val = result.one()

    stats = {
        "total_orders": int(total_orders),
        "total_revenue": f"{float(total_revenue):.2f}",
        "average_order_value": f"{float(avg_order_val):.2f}"
    }

    # 4. Store in Redis with jittered TTL (120 seconds base)
    effective_ttl = calculate_ttl(DASHBOARD_TTL)
    try:
        await cache.set_json(cache_key, stats, ttl=effective_ttl)
        logger.info("Cached dashboard stats %s for %d s", cache_key, effective_ttl)
    except RedisError:
        logger.warning("Could not cache dashboard stats for %s", cache_key)

    # 5. Return result
    return {
        "source": "postgresql",
        "stats": stats
    }


# ==========================================
# Create Order Helper (POST /dashboard/orders)
# ==========================================

@router.post("/orders", status_code=status.HTTP_201_CREATED, response_model=OrderResponse)
async def create_order(
    payload: OrderCreate,
    db: DatabaseDependency
):
    created_at = payload.created_at or datetime.now(timezone.utc)
    order = Order(
        tenant_id=payload.tenant_id.strip().lower(),
        total_amount=payload.total_amount,
        status=payload.status,
        created_at=created_at
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order
