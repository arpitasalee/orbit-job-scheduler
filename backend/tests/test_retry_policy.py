import pytest
from app.models.models import RetryStrategy
from app.services.retry import compute_retry_delay_seconds


@pytest.mark.parametrize("attempt,expected", [(1, 5), (2, 5), (3, 5)])
def test_fixed_strategy(attempt, expected):
    assert compute_retry_delay_seconds(RetryStrategy.fixed, base_delay=5, max_delay=300, attempt=attempt) == expected


@pytest.mark.parametrize("attempt,expected", [(1, 5), (2, 10), (3, 15)])
def test_linear_strategy(attempt, expected):
    assert compute_retry_delay_seconds(RetryStrategy.linear, base_delay=5, max_delay=300, attempt=attempt) == expected


@pytest.mark.parametrize("attempt,expected", [(1, 5), (2, 10), (3, 20), (4, 40)])
def test_exponential_strategy(attempt, expected):
    assert compute_retry_delay_seconds(RetryStrategy.exponential, base_delay=5, max_delay=300, attempt=attempt) == expected


def test_delay_is_capped_at_max_delay():
    delay = compute_retry_delay_seconds(RetryStrategy.exponential, base_delay=100, max_delay=250, attempt=5)
    assert delay == 250
