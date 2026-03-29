"""Tests for agreement rate limiting."""

import pytest

from src.config import RateLimitConfig
from src.security.rate_limit import AgreementRateLimiter, RateLimitExceededError


def test_rate_limiter_blocks_over_limit(monkeypatch) -> None:
    limiter = AgreementRateLimiter(RateLimitConfig(requests_per_minute=2))
    times = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr("src.security.rate_limit.monotonic", lambda: next(times))
    limiter.check("agreement-1")
    limiter.check("agreement-1")
    with pytest.raises(RateLimitExceededError):
        limiter.check("agreement-1")
