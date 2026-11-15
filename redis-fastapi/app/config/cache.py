import random

# ==========================================
# Centralized Cache TTL Constants (in seconds)
# ==========================================

PRODUCT_DETAIL_TTL = 300       # 5 minutes
PRODUCT_LIST_TTL = 120         # 2 minutes
USER_PROFILE_TTL = 600         # 10 minutes
CATEGORY_TTL = 1800            # 30 minutes
DASHBOARD_TTL = 120            # 2 minutes
NEGATIVE_CACHE_TTL = 30        # 30 seconds


def calculate_ttl(base_ttl: int, jitter_percentage: float = 0.1) -> int:
    """
    Calculates dynamic TTL by adding random jitter to base_ttl.
    Prevents cache stampedes (thundering herd problem) where multiple keys
    expire simultaneously, hammering the primary database.

    :param base_ttl: Base expiration in seconds.
    :param jitter_percentage: Max percentage variance (default 10%, +/- 0.1).
    :return: Adjusted TTL integer with jitter applied.
    """
    if base_ttl <= 0:
        return 0
    max_jitter = int(base_ttl * jitter_percentage)
    if max_jitter <= 0:
        return base_ttl
    jitter = random.randint(-max_jitter, max_jitter)
    return max(1, base_ttl + jitter)
