def product_list_cache_key(
    page: int,
    limit: int,
    category: str | None = None,
    search: str | None = None,
    sort_by: str = "id",
    order: str = "desc"
) -> str:
    """
    Builds a normalized, deterministic Redis cache key for product listings.
    Normalizes string parameters (lowercase, trimmed) to prevent cache duplicates.
    """
    category_part = category.strip().lower() if category else "all"
    search_part = search.strip().lower() if search else "none"
    sort_part = sort_by.strip().lower() if sort_by else "id"
    order_part = order.strip().lower() if order else "desc"

    return (
        f"v1:products:list:"
        f"category:{category_part}:"
        f"search:{search_part}:"
        f"page:{page}:"
        f"limit:{limit}:"
        f"sort:{sort_part}:"
        f"order:{order_part}"
    )


def user_profile_cache_key(
    tenant_id: str,
    user_id: int
) -> str:
    """
    Builds a tenant-isolated Redis cache key for user profiles.
    Ensures that identical user IDs in different tenants do not collide.
    """
    tenant_part = tenant_id.strip().lower() if tenant_id else "default"
    return f"v1:tenant:{tenant_part}:user:{user_id}:profile"


def product_detail_cache_key(product_id: int) -> str:
    """
    Builds a versioned Redis cache key for an individual product detail.
    """
    return f"v1:product:{product_id}"
