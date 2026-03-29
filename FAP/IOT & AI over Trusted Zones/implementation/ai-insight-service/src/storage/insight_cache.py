"""Shared insight cache with Redis backend and deterministic keying."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any, Protocol

from src.config import CacheConfig

logger = logging.getLogger(__name__)


class InsightCache(Protocol):
    """Minimal cache contract for insight payloads."""

    def get(self, key: str) -> dict[str, Any] | None: ...

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None: ...


class NoopInsightCache:
    """No-op cache fallback when caching is disabled/unavailable."""

    def get(self, key: str) -> dict[str, Any] | None:
        return None

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        return None


class RedisInsightCache:
    """Redis-backed cache storing JSON-serializable payloads."""

    def __init__(
        self,
        *,
        redis_url: str,
        connect_timeout_seconds: float,
    ) -> None:
        try:
            import redis
        except ImportError as error:  # pragma: no cover - depends on environment
            raise RuntimeError("Redis dependency is not installed") from error

        self._client = redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=connect_timeout_seconds,
            socket_timeout=connect_timeout_seconds,
        )

    def get(self, key: str) -> dict[str, Any] | None:
        try:
            raw_value = self._client.get(key)
            if not raw_value:
                return None
            parsed = json.loads(raw_value)
        except Exception:
            logger.exception("insight_cache_read_failed", extra={"key": key})
            return None
        if not isinstance(parsed, dict):
            return None
        return parsed

    def set(self, key: str, value: dict[str, Any], ttl_seconds: int) -> None:
        try:
            payload = json.dumps(
                value,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            self._client.setex(key, ttl_seconds, payload)
        except Exception:
            logger.exception("insight_cache_write_failed", extra={"key": key})


def _normalize_dt(value: datetime) -> str:
    normalized = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return normalized.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def build_insight_cache_key(
    *,
    key_prefix: str,
    insight_type: str,
    agreement_id: str,
    asset_id: str,
    start_ts: datetime,
    end_ts: datetime,
    parameters: dict[str, Any],
) -> str:
    """Build stable cache key from strict request identity."""
    key_payload = {
        "insight_type": insight_type,
        "agreement_id": agreement_id,
        "asset_id": asset_id,
        "start_ts": _normalize_dt(start_ts),
        "end_ts": _normalize_dt(end_ts),
        "parameters": parameters,
    }
    digest = sha256(
        json.dumps(
            key_payload,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return f"{key_prefix}:{digest}"


def create_insight_cache(cache_config: CacheConfig) -> InsightCache:
    """Create configured cache backend with safe no-op fallback."""
    if not cache_config.enabled:
        return NoopInsightCache()
    backend = cache_config.backend.strip().lower()
    if backend != "redis":
        logger.warning("Unsupported cache backend '%s'; disabling cache", cache_config.backend)
        return NoopInsightCache()
    if not cache_config.redis_url:
        logger.warning("Cache is enabled but redis_url is empty; disabling cache")
        return NoopInsightCache()
    try:
        return RedisInsightCache(
            redis_url=cache_config.redis_url,
            connect_timeout_seconds=cache_config.connect_timeout_seconds,
        )
    except Exception:
        logger.exception("Failed to initialize Redis cache; disabling cache")
        return NoopInsightCache()
