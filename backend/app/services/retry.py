"""
Pure functions for computing the next retry delay. Kept isolated and
side-effect free so they're trivial to unit test.
"""
from app.models.models import RetryStrategy


def compute_retry_delay_seconds(strategy: RetryStrategy, base_delay: int, max_delay: int, attempt: int) -> int:
    """
    attempt: the retry attempt number about to be made (1 = first retry after
    the initial failed attempt).
    """
    if strategy == RetryStrategy.fixed:
        delay = base_delay
    elif strategy == RetryStrategy.linear:
        delay = base_delay * attempt
    elif strategy == RetryStrategy.exponential:
        delay = base_delay * (2 ** (attempt - 1))
    else:
        delay = base_delay
    return min(delay, max_delay)
