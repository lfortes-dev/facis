"""Build deterministic LLM context payloads from analytics outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from src.analytics.outliers import MetricSummary


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
