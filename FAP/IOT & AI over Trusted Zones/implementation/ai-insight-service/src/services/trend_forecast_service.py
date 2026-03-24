"""Service layer for energy trend and forecast context generation."""

from __future__ import annotations

from datetime import datetime
import logging
from time import perf_counter
from typing import Any, Literal

from src.analytics.trend_forecast import analyze_trend_forecast
from src.data.trino_client import TrinoQueryClient
from src.llm.context_builder import build_trend_forecast_context

logger = logging.getLogger(__name__)


def _safe_iso(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _series_bounds(rows: list[dict[str, Any]], timestamp_key: str) -> dict[str, Any]:
    if not rows:
        return {"count": 0, "first": None, "last": None}
    values = [row.get(timestamp_key) for row in rows if row.get(timestamp_key) is not None]
    if not values:
        return {"count": len(rows), "first": None, "last": None}
    ordered = sorted(values, key=lambda item: str(item))
    return {
        "count": len(rows),
        "first": _safe_iso(ordered[0]),
        "last": _safe_iso(ordered[-1]),
    }


class TrendForecastService:
    """Orchestrates Gold-series queries, trend analytics, and context output."""

    def __init__(self, trino_client: TrinoQueryClient) -> None:
        self._trino_client = trino_client

    def generate_trend_forecast_context(
        self,
        *,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
        forecast_alpha: float = 0.6,
        trend_epsilon: float = 0.02,
        daily_overview_strategy: Literal["strict_daily", "fallback_hourly"] = "strict_daily",
    ) -> dict[str, Any]:
        """Generate trend and next-24h forecast context for LLM summarization."""
        started_at = perf_counter()
        if start_ts >= end_ts:
            raise ValueError("start_ts must be earlier than end_ts")
        if forecast_alpha <= 0 or forecast_alpha > 1:
            raise ValueError("forecast_alpha must be within (0, 1]")
        if trend_epsilon < 0:
            raise ValueError("trend_epsilon must be >= 0")

        dataset = self._trino_client.fetch_energy_trend_forecast_rows(
            start_ts=start_ts,
            end_ts=end_ts,
        )
        hourly_rows = dataset.get("hourly", [])
        daily_cost_rows = dataset.get("daily_cost", [])
        daily_pv_rows = dataset.get("daily_pv", [])

        trend_result = analyze_trend_forecast(
            hourly_rows=hourly_rows,
            daily_cost_rows=daily_cost_rows,
            daily_pv_rows=daily_pv_rows,
            alpha=forecast_alpha,
            trend_epsilon=trend_epsilon,
            daily_overview_strategy=daily_overview_strategy,
        )
        data_availability = {
            "hourly_net_grid_weather": _series_bounds(hourly_rows, "hour"),
            "daily_cost": _series_bounds(daily_cost_rows, "cost_date"),
            "daily_pv_self_consumption": _series_bounds(daily_pv_rows, "sc_date"),
        }
        context = build_trend_forecast_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
            total_rows=len(hourly_rows),
            trend_result=trend_result,
            data_availability=data_availability,
        )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "trend_forecast_completed start_ts=%s end_ts=%s timezone=%s "
            "hourly_rows=%d forecast_points=%d elapsed_ms=%d",
            start_ts.isoformat(),
            end_ts.isoformat(),
            timezone,
            len(hourly_rows),
            len(trend_result.forecast_24h),
            elapsed_ms,
        )
        if len(hourly_rows) == 0:
            logger.warning(
                "trend_forecast_no_data start_ts=%s end_ts=%s timezone=%s",
                start_ts.isoformat(),
                end_ts.isoformat(),
                timezone,
            )
        return context
