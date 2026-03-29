"""In-memory agreement-based rate limiting."""

from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
from time import monotonic

from src.config import RateLimitConfig


class RateLimitExceededError(Exception):
    """Raised when request exceeds configured rate limit."""

    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class AgreementRateLimiter:
    """Simple in-memory sliding-window limiter keyed by agreement id."""

    def __init__(self, config: RateLimitConfig) -> None:
        self._config = config
        self._lock = Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, agreement_id: str) -> None:
        if not self._config.enabled:
            return
        now = monotonic()
        window_start = now - 60.0
        with self._lock:
            entries = self._events[agreement_id]
            while entries and entries[0] < window_start:
                entries.popleft()
            if len(entries) >= self._config.requests_per_minute:
                retry_after = max(1, int(60 - (now - entries[0])))
                raise RateLimitExceededError(retry_after_seconds=retry_after)
            entries.append(now)
