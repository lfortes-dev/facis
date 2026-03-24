"""Unit tests for trend/forecast analytics and context builder."""

from datetime import datetime, timezone

from src.analytics.trend_forecast import analyze_trend_forecast
from src.llm.context_builder import build_trend_forecast_context


def _hourly_row(hour: int, day: int, consumption: float, generation: float, net: float, cost: float):
    return {
        "hour": f"2026-03-{day:02d}T{hour:02d}:00:00+00:00",
        "avg_consumption_kw": consumption,
        "avg_generation_kw": generation,
        "net_grid_kw": net,
        "avg_price_eur_per_kwh": 0.2,
        "estimated_hourly_cost_eur": cost,
        "avg_temperature_c": 18.0,
        "avg_irradiance_w_m2": 120.0,
        "avg_humidity_pct": 60.0,
        "avg_wind_speed_ms": 3.0,
        "avg_cloud_cover_pct": 40.0,
    }


def test_analyze_trend_forecast_returns_24_point_forecast() -> None:
    hourly_rows = []
    for day in (1, 2):
        for hour in range(24):
            baseline = 40.0 + hour * 0.5
            hourly_rows.append(
                _hourly_row(
                    hour,
                    day,
                    consumption=baseline + 10.0,
                    generation=10.0,
                    net=baseline,
                    cost=baseline * 0.12,
                )
            )
    daily_cost_rows = [
        {"cost_date": "2026-03-01", "total_consumption_kw": 300.0},
        {"cost_date": "2026-03-02", "total_consumption_kw": 320.0},
    ]
    daily_pv_rows = [
        {"sc_date": "2026-03-01", "self_consumption_ratio": 0.61},
        {"sc_date": "2026-03-02", "self_consumption_ratio": 0.58},
    ]

    result = analyze_trend_forecast(
        hourly_rows=hourly_rows,
        daily_cost_rows=daily_cost_rows,
        daily_pv_rows=daily_pv_rows,
        trend_epsilon=0.02,
        daily_overview_strategy="strict_daily",
    )

    assert len(result.forecast_24h) == 24
    assert result.trend_signals["net_grid_kw"]["direction"] in {"up", "stable", "down"}
    assert "ma_24h" in result.moving_averages["avg_consumption_kw"]
    assert result.daily_overview["daily_cost_points"] == 2


def test_build_trend_forecast_context_has_stable_keys() -> None:
    result = analyze_trend_forecast(
        hourly_rows=[],
        daily_cost_rows=[],
        daily_pv_rows=[],
        daily_overview_strategy="strict_daily",
    )
    context = build_trend_forecast_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        timezone="UTC",
        total_rows=0,
        trend_result=result,
        data_availability={
            "hourly_net_grid_weather": {"count": 0, "first": None, "last": None},
            "daily_cost": {"count": 0, "first": None, "last": None},
            "daily_pv_self_consumption": {"count": 0, "first": None, "last": None},
        },
    )

    assert context["summary"]["forecast_points"] == 0
    assert "trend_signals" in context
    assert "moving_averages" in context
    assert "seasonality_patterns" in context
    assert "daily_overview" in context
    assert "data_availability" in context


def test_analyze_trend_forecast_hourly_fallback_for_daily_overview() -> None:
    hourly_rows = [
        _hourly_row(0, 1, consumption=10.0, generation=5.0, net=5.0, cost=1.0),
        _hourly_row(1, 1, consumption=11.0, generation=5.5, net=5.5, cost=1.1),
        _hourly_row(0, 2, consumption=15.0, generation=7.5, net=7.5, cost=1.6),
        _hourly_row(1, 2, consumption=16.0, generation=8.0, net=8.0, cost=1.7),
    ]
    result = analyze_trend_forecast(
        hourly_rows=hourly_rows,
        daily_cost_rows=[],
        daily_pv_rows=[],
        daily_overview_strategy="fallback_hourly",
    )

    assert result.daily_overview["source"] == "hourly_fallback"
    assert result.daily_overview["daily_cost_points"] == 2
