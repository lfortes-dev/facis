"""Tests for insight cache keying helpers."""

from datetime import UTC, datetime

from src.storage.insight_cache import build_insight_cache_key


def test_cache_key_is_stable_for_same_request_identity() -> None:
    key1 = build_insight_cache_key(
        key_prefix="ai-insight:cache:v1",
        insight_type="energy-summary",
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 3, 1, tzinfo=UTC),
        end_ts=datetime(2026, 3, 2, tzinfo=UTC),
        parameters={
            "timezone": "UTC",
            "forecast_alpha": 0.6,
            "trend_epsilon": 0.02,
            "daily_overview_strategy": "strict_daily",
        },
    )
    key2 = build_insight_cache_key(
        key_prefix="ai-insight:cache:v1",
        insight_type="energy-summary",
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 3, 1, tzinfo=UTC),
        end_ts=datetime(2026, 3, 2, tzinfo=UTC),
        parameters={
            "daily_overview_strategy": "strict_daily",
            "trend_epsilon": 0.02,
            "forecast_alpha": 0.6,
            "timezone": "UTC",
        },
    )
    assert key1 == key2


def test_cache_key_changes_when_output_affecting_parameter_changes() -> None:
    strict_key = build_insight_cache_key(
        key_prefix="ai-insight:cache:v1",
        insight_type="energy-summary",
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 3, 1, tzinfo=UTC),
        end_ts=datetime(2026, 3, 2, tzinfo=UTC),
        parameters={
            "timezone": "UTC",
            "forecast_alpha": 0.6,
            "trend_epsilon": 0.02,
            "daily_overview_strategy": "strict_daily",
        },
    )
    fallback_key = build_insight_cache_key(
        key_prefix="ai-insight:cache:v1",
        insight_type="energy-summary",
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 3, 1, tzinfo=UTC),
        end_ts=datetime(2026, 3, 2, tzinfo=UTC),
        parameters={
            "timezone": "UTC",
            "forecast_alpha": 0.6,
            "trend_epsilon": 0.02,
            "daily_overview_strategy": "fallback_hourly",
        },
    )
    assert strict_key != fallback_key
