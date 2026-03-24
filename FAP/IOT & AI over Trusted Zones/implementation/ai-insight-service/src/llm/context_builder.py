"""Build deterministic LLM context payloads from analytics outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.analytics.outliers import MetricSummary
from src.analytics.smart_city_correlation import CorrelationResult
from src.analytics.trend_forecast import TrendForecastResult


def _round_float(value: float) -> float:
    return round(value, 4)


def _to_iso(value: datetime) -> str:
    return value.isoformat()


def build_structured_context(
    *,
    start_ts: datetime,
    end_ts: datetime,
    timezone: str,
    total_rows: int,
    selected_metrics: list[str],
    summaries: list[MetricSummary],
    outlier_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create compact structured context sections for prompt consumption."""
    baseline_stats = [
        {
            "metric": summary.metric,
            "count": summary.count,
            "min": _round_float(summary.min),
            "max": _round_float(summary.max),
            "mean": _round_float(summary.mean),
            "median": _round_float(summary.median),
            "mad": _round_float(summary.mad),
        }
        for summary in summaries
    ]

    cost_anomalies = [event for event in outlier_events if "cost" in event["metric"].lower()]
    outlier_events_sorted = sorted(
        outlier_events,
        key=lambda event: (event.get("timestamp", ""), event.get("metric", "")),
    )

    event_counts: dict[str, int] = {}
    for event in outlier_events_sorted:
        metric = str(event["metric"])
        event_counts[metric] = event_counts.get(metric, 0) + 1

    hints: list[str] = []
    if outlier_events_sorted:
        hints.append("Detected statistically unusual points using robust z-score (MAD).")
    else:
        hints.append("No robust outliers detected for the selected metrics and window.")

    if cost_anomalies:
        hints.append("Cost-related anomalies were detected and may reflect tariff or usage shifts.")

    if not selected_metrics:
        hints.append(
            "No expected consumption/generation/cost metric columns were found in result schema."
        )

    return {
        "window": {
            "start_ts": _to_iso(start_ts),
            "end_ts": _to_iso(end_ts),
            "timezone": timezone,
            "rows_analyzed": total_rows,
        },
        "baseline_stats": baseline_stats,
        "outlier_events": outlier_events_sorted,
        "cost_anomalies": cost_anomalies,
        "narrative_hints": hints,
        "summary": {
            "total_outliers": len(outlier_events_sorted),
            "outliers_by_metric": event_counts,
            "selected_metrics": selected_metrics,
        },
    }


def build_smart_city_correlation_context(
    *,
    start_ts: datetime,
    end_ts: datetime,
    timezone: str,
    total_rows: int,
    correlation_result: CorrelationResult,
) -> dict[str, Any]:
    """Create structured context for Smart City event/infrastructure correlation."""
    patterns = sorted(
        correlation_result.event_response_patterns,
        key=lambda pattern: (
            str(pattern.get("event_date", "")),
            str(pattern.get("zone_id", "")),
            str(pattern.get("event_type", "")),
        ),
    )
    high_confidence_links = sorted(
        correlation_result.high_confidence_links,
        key=lambda item: (
            str(item.get("event_date", "")),
            str(item.get("zone_id", "")),
            str(item.get("event_type", "")),
        ),
    )

    hints: list[str] = []
    if patterns:
        hints.append(
            "Detected event-to-streetlight response patterns using hybrid baseline and lag analysis."
        )
    else:
        hints.append("No event-to-infrastructure response patterns detected in the selected window.")
    if high_confidence_links:
        hints.append("High-confidence links indicate strong and temporally close infrastructure responses.")
    else:
        hints.append("No high-confidence links identified; responses are weak or diffuse across lag windows.")

    confidence_counts = {"high": 0, "medium": 0, "low": 0}
    for pattern in patterns:
        confidence = str(pattern.get("confidence", "low"))
        if confidence not in confidence_counts:
            confidence = "low"
        confidence_counts[confidence] += 1

    return {
        "window": {
            "start_ts": _to_iso(start_ts),
            "end_ts": _to_iso(end_ts),
            "timezone": timezone,
            "rows_analyzed": total_rows,
        },
        "event_response_patterns": patterns,
        "lag_distribution": correlation_result.lag_distribution,
        "zone_response_summary": correlation_result.zone_response_summary,
        "high_confidence_links": high_confidence_links,
        "narrative_hints": hints,
        "summary": {
            "total_patterns": len(patterns),
            "high_confidence_links": len(high_confidence_links),
            "confidence_distribution": confidence_counts,
        },
    }


def build_trend_forecast_context(
    *,
    start_ts: datetime,
    end_ts: datetime,
    timezone: str,
    total_rows: int,
    trend_result: TrendForecastResult,
    data_availability: dict[str, Any],
) -> dict[str, Any]:
    """Create structured context for trend and 24h forecast summarization."""
    forecast_24h = sorted(
        trend_result.forecast_24h,
        key=lambda point: str(point.get("timestamp", "")),
    )
    trend_items = sorted(trend_result.trend_signals.items(), key=lambda item: item[0])
    moving_average_items = sorted(trend_result.moving_averages.items(), key=lambda item: item[0])
    seasonality_items = sorted(trend_result.seasonality_patterns.items(), key=lambda item: item[0])

    hints = list(trend_result.confidence_notes)
    if forecast_24h:
        hints.append("Forecast uses hourly seasonality plus recent-level adjustment baseline model.")
    else:
        hints.append("Forecast output is empty due to insufficient hourly history in selected window.")

    return {
        "window": {
            "start_ts": _to_iso(start_ts),
            "end_ts": _to_iso(end_ts),
            "timezone": timezone,
            "rows_analyzed": total_rows,
        },
        "trend_signals": {key: value for key, value in trend_items},
        "moving_averages": {key: value for key, value in moving_average_items},
        "seasonality_patterns": {key: value for key, value in seasonality_items},
        "forecast_24h": forecast_24h,
        "daily_overview": trend_result.daily_overview,
        "data_availability": data_availability,
        "narrative_hints": hints,
        "summary": {
            "forecast_points": len(forecast_24h),
            "tracked_metrics": [key for key, _ in trend_items],
            "daily_cost_points": trend_result.daily_overview.get("daily_cost_points", 0),
            "daily_pv_points": trend_result.daily_overview.get("daily_pv_points", 0),
        },
    }
