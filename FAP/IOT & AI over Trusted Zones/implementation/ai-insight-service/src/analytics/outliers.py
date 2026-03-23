"""Robust outlier detection for hourly net-grid metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean, median
from typing import Any


@dataclass(frozen=True)
class MetricSummary:
    """Baseline summary statistics for a metric."""

    metric: str
    count: int
    min: float
    max: float
    mean: float
    median: float
    mad: float


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _median_abs_deviation(values: list[float], med: float) -> float:
    return median([abs(v - med) for v in values])


def _safe_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def summarize_metric(metric: str, values: list[float]) -> MetricSummary:
    """Build baseline stats used by LLM context."""
    med = median(values)
    mad = _median_abs_deviation(values, med)
    return MetricSummary(
        metric=metric,
        count=len(values),
        min=min(values),
        max=max(values),
        mean=mean(values),
        median=med,
        mad=mad,
    )


def detect_metric_outliers(
    records: list[dict[str, Any]],
    metric: str,
    timestamp_column: str,
    threshold: float = 3.5,
) -> tuple[list[dict[str, Any]], MetricSummary | None]:
    """Detect robust-z outliers for one metric."""
    pairs: list[tuple[dict[str, Any], float]] = []
    for record in records:
        value = _to_float(record.get(metric))
        if value is None:
            continue
        pairs.append((record, value))

    if len(pairs) < 3:
        return [], None

    values = [value for _, value in pairs]
    summary = summarize_metric(metric=metric, values=values)
    if summary.mad == 0:
        return [], summary

    events: list[dict[str, Any]] = []
    scale = 1.4826 * summary.mad
    for record, value in pairs:
        robust_z = (value - summary.median) / scale
        if abs(robust_z) < threshold:
            continue
        events.append(
            {
                "timestamp": _safe_timestamp(record.get(timestamp_column)),
                "metric": metric,
                "value": value,
                "baseline_median": summary.median,
                "robust_z": robust_z,
                "event_type": "spike" if robust_z > 0 else "drop",
            }
        )
    return events, summary
