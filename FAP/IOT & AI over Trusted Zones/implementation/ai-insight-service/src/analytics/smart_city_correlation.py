"""Hybrid Smart City correlation analytics for Gold-layer event/infrastructure data."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from statistics import median
from typing import Any


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _to_date_string(value: Any) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _to_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if value is None:
        return None
    text = str(value)
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _median_abs_deviation(values: list[float], med: float) -> float:
    return median([abs(v - med) for v in values])


def _safe_z(value: float, med: float, mad: float) -> float:
    if mad <= 0:
        return 0.0
    scale = 1.4826 * mad
    if scale <= 0:
        return 0.0
    return (value - med) / scale


def _percent_shift(value: float, baseline: float) -> float:
    if baseline == 0:
        return 0.0
    return ((value - baseline) / abs(baseline)) * 100.0


def _lag_bucket(lag_hours: float) -> str:
    if lag_hours < 6:
        return "0-6h"
    if lag_hours < 24:
        return "6-24h"
    return "24-48h"


def _score_to_confidence(score: float) -> str:
    if score >= 0.8:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


@dataclass(frozen=True)
class CorrelationResult:
    """Structured output from hybrid correlation analysis."""

    event_response_patterns: list[dict[str, Any]]
    lag_distribution: dict[str, int]
    zone_response_summary: list[dict[str, Any]]
    high_confidence_links: list[dict[str, Any]]


def analyze_event_infrastructure_correlation(
    rows: list[dict[str, Any]],
) -> CorrelationResult:
    """Detect event-to-streetlight response patterns with hybrid scoring."""
    if not rows:
        return CorrelationResult(
            event_response_patterns=[],
            lag_distribution={"0-6h": 0, "6-24h": 0, "24-48h": 0},
            zone_response_summary=[],
            high_confidence_links=[],
        )

    zone_power_values: dict[str, list[float]] = defaultdict(list)
    zone_dimming_values: dict[str, list[float]] = defaultdict(list)
    event_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        zone = str(row.get("zone_id", ""))
        power = _to_float(row.get("total_power_w"))
        dimming = _to_float(row.get("avg_dimming_pct"))
        if power is not None:
            zone_power_values[zone].append(power)
        if dimming is not None:
            zone_dimming_values[zone].append(dimming)
        key = (
            _to_date_string(row.get("event_date")),
            zone,
            str(row.get("event_type", "unknown")),
        )
        event_groups[key].append(row)

    zone_baselines: dict[str, dict[str, float]] = {}
    for zone, values in zone_power_values.items():
        power_med = median(values) if values else 0.0
        power_mad = _median_abs_deviation(values, power_med) if values else 0.0
        dim_values = zone_dimming_values.get(zone, [])
        dim_med = median(dim_values) if dim_values else 0.0
        dim_mad = _median_abs_deviation(dim_values, dim_med) if dim_values else 0.0
        zone_baselines[zone] = {
            "power_median": power_med,
            "power_mad": power_mad,
            "dimming_median": dim_med,
            "dimming_mad": dim_mad,
        }

    lag_distribution = {"0-6h": 0, "6-24h": 0, "24-48h": 0}
    zone_agg: dict[str, dict[str, float]] = {}
    patterns: list[dict[str, Any]] = []
    high_confidence_links: list[dict[str, Any]] = []

    for event_key in sorted(event_groups):
        event_date, zone_id, event_type = event_key
        group_rows = sorted(
            event_groups[event_key],
            key=lambda item: str(item.get("hour", "")),
        )
        baseline = zone_baselines.get(
            zone_id,
            {
                "power_median": 0.0,
                "power_mad": 0.0,
                "dimming_median": 0.0,
                "dimming_mad": 0.0,
            },
        )

        power_values = [
            value
            for value in (_to_float(item.get("total_power_w")) for item in group_rows)
            if value is not None
        ]
        dimming_values = [
            value
            for value in (_to_float(item.get("avg_dimming_pct")) for item in group_rows)
            if value is not None
        ]
        event_avg_power = sum(power_values) / len(power_values) if power_values else 0.0
        event_avg_dimming = (
            sum(dimming_values) / len(dimming_values) if dimming_values else 0.0
        )

        power_z = _safe_z(event_avg_power, baseline["power_median"], baseline["power_mad"])
        dimming_z = _safe_z(
            event_avg_dimming,
            baseline["dimming_median"],
            baseline["dimming_mad"],
        )

        local_buckets = {"0-6h": 0, "6-24h": 0, "24-48h": 0}
        event_start = _to_datetime(f"{event_date}T00:00:00+00:00")
        if event_start is None:
            event_start = datetime.fromisoformat("1970-01-01T00:00:00+00:00")

        for item in group_rows:
            hour_dt = _to_datetime(item.get("hour"))
            if hour_dt is None:
                continue
            lag_hours = (hour_dt - event_start).total_seconds() / 3600.0
            bucket = _lag_bucket(lag_hours)
            local_buckets[bucket] += 1
            lag_distribution[bucket] += 1

        lag_strength = (
            (local_buckets["0-6h"] * 1.0)
            + (local_buckets["6-24h"] * 0.6)
            + (local_buckets["24-48h"] * 0.3)
        ) / max(1, len(group_rows))

        severity = _to_float(group_rows[0].get("avg_severity")) or 0.0
        event_count = int(_to_float(group_rows[0].get("event_count")) or 0.0)
        active_count = int(_to_float(group_rows[0].get("active_count")) or 0.0)
        severity_factor = min(1.0, severity / 3.0)
        activity_factor = min(1.0, active_count / max(1, event_count)) if event_count else 0.0
        anomaly_strength = min(1.0, (abs(power_z) + abs(dimming_z)) / 6.0)

        response_score = (
            (0.45 * anomaly_strength)
            + (0.35 * lag_strength)
            + (0.2 * max(severity_factor, activity_factor))
        )
        confidence = _score_to_confidence(response_score)

        pattern = {
            "event_date": event_date,
            "zone_id": zone_id,
            "event_type": event_type,
            "event_count": event_count,
            "avg_severity": round(severity, 4),
            "active_count": active_count,
            "hours_analyzed": len(group_rows),
            "lag_bucket_counts": local_buckets,
            "baseline": {
                "power_median": round(baseline["power_median"], 4),
                "dimming_median": round(baseline["dimming_median"], 4),
            },
            "response": {
                "event_avg_power_w": round(event_avg_power, 4),
                "event_avg_dimming_pct": round(event_avg_dimming, 4),
                "power_shift_pct": round(
                    _percent_shift(event_avg_power, baseline["power_median"]),
                    4,
                ),
                "dimming_shift_pct": round(
                    _percent_shift(event_avg_dimming, baseline["dimming_median"]),
                    4,
                ),
                "power_shift_robust_z": round(power_z, 4),
                "dimming_shift_robust_z": round(dimming_z, 4),
            },
            "response_score": round(response_score, 4),
            "confidence": confidence,
        }
        patterns.append(pattern)

        if confidence == "high":
            high_confidence_links.append(
                {
                    "event_date": event_date,
                    "zone_id": zone_id,
                    "event_type": event_type,
                    "response_score": round(response_score, 4),
                }
            )

        if zone_id not in zone_agg:
            zone_agg[zone_id] = {
                "patterns": 0.0,
                "high_confidence_patterns": 0.0,
                "avg_response_score_total": 0.0,
            }
        zone_agg[zone_id]["patterns"] += 1
        zone_agg[zone_id]["avg_response_score_total"] += response_score
        if confidence == "high":
            zone_agg[zone_id]["high_confidence_patterns"] += 1

    zone_response_summary = []
    for zone_id in sorted(zone_agg):
        aggregate = zone_agg[zone_id]
        patterns_count = int(aggregate["patterns"])
        avg_score = aggregate["avg_response_score_total"] / max(1, patterns_count)
        zone_response_summary.append(
            {
                "zone_id": zone_id,
                "patterns": patterns_count,
                "high_confidence_patterns": int(aggregate["high_confidence_patterns"]),
                "avg_response_score": round(avg_score, 4),
            }
        )

    return CorrelationResult(
        event_response_patterns=patterns,
        lag_distribution=lag_distribution,
        zone_response_summary=zone_response_summary,
        high_confidence_links=high_confidence_links,
    )
