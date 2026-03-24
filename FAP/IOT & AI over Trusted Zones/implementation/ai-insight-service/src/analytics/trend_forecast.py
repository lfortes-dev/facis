"""Trend and forecast analytics for energy Gold views."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import mean
from typing import Any, Literal


METRICS = ("avg_consumption_kw", "net_grid_kw", "estimated_hourly_cost_eur")


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


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


def _moving_average(values: list[float], window: int) -> float | None:
    if len(values) < window:
        return None
    return mean(values[-window:])


def _trend_direction(values: list[float], points: int = 24, epsilon: float = 0.02) -> dict[str, Any]:
    if len(values) < 2:
        return {"direction": "stable", "slope_per_step": 0.0}
    tail = values[-points:] if len(values) >= points else values
    slope = (tail[-1] - tail[0]) / max(1, len(tail) - 1)
    baseline = max(abs(tail[0]), 1.0)
    normalized = slope / baseline
    if normalized > epsilon:
        direction = "up"
    elif normalized < -epsilon:
        direction = "down"
    else:
        direction = "stable"
    return {"direction": direction, "slope_per_step": round(slope, 4)}


def _daily_trend(values: list[float]) -> str:
    if len(values) < 2:
        return "stable"
    delta = values[-1] - values[0]
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "stable"


def _safe_timestamp(value: Any) -> datetime | None:
    dt_value = _to_datetime(value)
    return dt_value


def _build_hourly_daily_fallback(hourly_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_day: dict[str, dict[str, list[float]]] = {}
    for row in hourly_rows:
        ts = _safe_timestamp(row.get("hour"))
        if ts is None:
            continue
        day_key = ts.date().isoformat()
        if day_key not in by_day:
            by_day[day_key] = {"consumption": [], "generation": []}
        cons = _to_float(row.get("avg_consumption_kw"))
        gen = _to_float(row.get("avg_generation_kw"))
        if cons is not None:
            by_day[day_key]["consumption"].append(cons)
        if gen is not None:
            by_day[day_key]["generation"].append(gen)

    ordered_days = sorted(by_day)
    daily_consumption: list[float] = []
    daily_self_ratio: list[float] = []
    for day in ordered_days:
        cons_values = by_day[day]["consumption"]
        gen_values = by_day[day]["generation"]
        if cons_values:
            daily_consumption.append(sum(cons_values))
        if cons_values and gen_values:
            cons_sum = sum(cons_values)
            gen_sum = sum(gen_values)
            if gen_sum > 0:
                self_ratio = min(cons_sum, gen_sum) / gen_sum
            else:
                self_ratio = 0.0
            daily_self_ratio.append(self_ratio)

    return {
        "daily_cost_points": len(daily_consumption),
        "daily_pv_points": len(daily_self_ratio),
        "consumption_trend_daily": _daily_trend(daily_consumption),
        "self_consumption_trend_daily": _daily_trend(daily_self_ratio),
        "source": "hourly_fallback",
    }


@dataclass(frozen=True)
class TrendForecastResult:
    """Structured analytics output for trend and forecast pipeline."""

    trend_signals: dict[str, Any]
    moving_averages: dict[str, Any]
    seasonality_patterns: dict[str, Any]
    forecast_24h: list[dict[str, Any]]
    confidence_notes: list[str]
    daily_overview: dict[str, Any]


def analyze_trend_forecast(
    *,
    hourly_rows: list[dict[str, Any]],
    daily_cost_rows: list[dict[str, Any]],
    daily_pv_rows: list[dict[str, Any]],
    alpha: float = 0.6,
    trend_epsilon: float = 0.02,
    daily_overview_strategy: Literal["strict_daily", "fallback_hourly"] = "strict_daily",
) -> TrendForecastResult:
    """Compute moving averages, trend direction, seasonality, and next-24h forecast."""
    sorted_hourly = sorted(hourly_rows, key=lambda item: str(item.get("hour", "")))
    series: dict[str, list[float]] = {metric: [] for metric in METRICS}
    series_by_hour: dict[str, dict[int, list[float]]] = {
        metric: {hour: [] for hour in range(24)} for metric in METRICS
    }
    timestamps: list[datetime] = []

    for row in sorted_hourly:
        ts = _to_datetime(row.get("hour"))
        if ts is not None:
            timestamps.append(ts)
        for metric in METRICS:
            value = _to_float(row.get(metric))
            if value is None:
                continue
            series[metric].append(value)
            if ts is not None:
                series_by_hour[metric][ts.hour].append(value)

    moving_averages: dict[str, Any] = {}
    trend_signals: dict[str, Any] = {}
    seasonality_patterns: dict[str, Any] = {}
    for metric in METRICS:
        values = series[metric]
        ma6 = _moving_average(values, 6)
        ma24 = _moving_average(values, 24)
        moving_averages[metric] = {
            "ma_6h": round(ma6, 4) if ma6 is not None else None,
            "ma_24h": round(ma24, 4) if ma24 is not None else None,
            "latest_value": round(values[-1], 4) if values else None,
        }
        trend_signals[metric] = _trend_direction(values, epsilon=trend_epsilon)
        seasonality_patterns[metric] = {
            str(hour): (
                round(mean(hour_values), 4) if hour_values else None
            )
            for hour, hour_values in series_by_hour[metric].items()
        }

    forecast_24h: list[dict[str, Any]] = []
    seasonality_means = {
        metric: mean([v for v in seasonality_patterns[metric].values() if v is not None])
        if any(v is not None for v in seasonality_patterns[metric].values())
        else 0.0
        for metric in METRICS
    }
    reference_time = timestamps[-1] if timestamps else None
    for step in range(1, 25):
        if reference_time is None:
            break
        target_ts = reference_time + timedelta(hours=step)
        point: dict[str, Any] = {"timestamp": target_ts.isoformat()}
        for metric in METRICS:
            values = series[metric]
            recent_level = mean(values[-24:]) if values else 0.0
            seasonal = seasonality_patterns[metric].get(str(target_ts.hour))
            seasonal_value = seasonal if seasonal is not None else seasonality_means[metric]
            forecast_value = recent_level + (alpha * (seasonal_value - seasonality_means[metric]))
            point[metric] = round(forecast_value, 4)
        forecast_24h.append(point)

    confidence_notes: list[str] = []
    if not sorted_hourly:
        confidence_notes.append("No hourly rows available; forecast cannot be computed reliably.")
    else:
        for metric in METRICS:
            total = len(sorted_hourly)
            missing = total - len(series[metric])
            if total > 0 and (missing / total) > 0.15:
                confidence_notes.append(
                    f"{metric}: elevated missingness ({missing}/{total}) lowers forecast confidence."
                )
    if not confidence_notes:
        confidence_notes.append("Recent history coverage is sufficient for deterministic baseline forecasting.")

    cost_values = [
        value
        for value in (_to_float(item.get("total_consumption_kw")) for item in daily_cost_rows)
        if value is not None
    ]
    self_ratio_values = [
        value
        for value in (_to_float(item.get("self_consumption_ratio")) for item in daily_pv_rows)
        if value is not None
    ]
    daily_overview = {
        "daily_cost_points": len(daily_cost_rows),
        "daily_pv_points": len(daily_pv_rows),
        "consumption_trend_daily": _daily_trend(cost_values),
        "self_consumption_trend_daily": _daily_trend(self_ratio_values),
        "source": "daily_views",
    }
    if (
        daily_overview_strategy == "fallback_hourly"
        and len(daily_cost_rows) == 0
        and len(daily_pv_rows) == 0
    ):
        daily_overview = _build_hourly_daily_fallback(sorted_hourly)
        confidence_notes.append(
            "Daily views were empty; daily_overview was estimated from hourly series fallback."
        )

    return TrendForecastResult(
        trend_signals=trend_signals,
        moving_averages=moving_averages,
        seasonality_patterns=seasonality_patterns,
        forecast_24h=forecast_24h,
        confidence_notes=confidence_notes,
        daily_overview=daily_overview,
    )
