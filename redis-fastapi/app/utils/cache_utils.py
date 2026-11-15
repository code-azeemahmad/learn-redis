import random


def get_cache_ttl(
    base_ttl: int,
    jitter: int = 60
) -> int:
    """
    Calculates a cache TTL with random jitter (+/- jitter seconds)
    to prevent cache stampedes (thundering herd).

    :param base_ttl: Base TTL in seconds.
    :param jitter: Maximum seconds of random variance (+/- jitter). Default is 60.
    :return: Jittered TTL as an integer.
    """
    if base_ttl <= 0:
        return 0
    jitter_variance = random.randint(-jitter, jitter)
    return max(1, base_ttl + jitter_variance)
