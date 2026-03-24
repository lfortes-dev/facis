"""Unit tests for trend/forecast service orchestration."""

from datetime import datetime, timezone

from src.services.trend_forecast_service import TrendForecastService


class _FakeTrinoClient:
    def __init__(self, dataset: dict[str, list[dict[str, object]]]) -> None:
        self.dataset = dataset
        self.calls: list[dict[str, datetime]] = []

    def fetch_energy_trend_forecast_rows(
        self,
        start_ts: datetime,
        end_ts: datetime,
    ) -> dict[str, list[dict[str, object]]]:
        self.calls.append({"start_ts": start_ts, "end_ts": end_ts})
        return self.dataset


def test_generate_trend_forecast_context_empty_hourly() -> None:
    service = TrendForecastService(
        trino_client=_FakeTrinoClient(
            dataset={"hourly": [], "daily_cost": [], "daily_pv": []}
        )  # type: ignore[arg-type]
    )
    context = service.generate_trend_forecast_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        timezone="UTC",
        daily_overview_strategy="fallback_hourly",
    )

    assert context["window"]["rows_analyzed"] == 0
    assert context["summary"]["forecast_points"] == 0
    assert context["data_availability"]["hourly_net_grid_weather"]["count"] == 0


def test_generate_trend_forecast_context_validates_time_window() -> None:
    service = TrendForecastService(
        trino_client=_FakeTrinoClient(
            dataset={"hourly": [], "daily_cost": [], "daily_pv": []}
        )  # type: ignore[arg-type]
    )
    try:
        service.generate_trend_forecast_context(
            start_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
            end_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
            timezone="UTC",
        )
        assert False, "expected ValueError for invalid time window"
    except ValueError as error:
        assert "earlier" in str(error)


def test_generate_trend_forecast_context_invokes_fetch() -> None:
    fake = _FakeTrinoClient(
        dataset={
            "hourly": [
                {
                    "hour": "2026-03-01T00:00:00+00:00",
                    "avg_consumption_kw": 52.0,
                    "avg_generation_kw": 10.0,
                    "net_grid_kw": 42.0,
                    "avg_price_eur_per_kwh": 0.2,
                    "estimated_hourly_cost_eur": 8.4,
                }
            ],
            "daily_cost": [{"cost_date": "2026-03-01", "total_consumption_kw": 300.0}],
            "daily_pv": [{"sc_date": "2026-03-01", "self_consumption_ratio": 0.6}],
        }
    )
    service = TrendForecastService(trino_client=fake)  # type: ignore[arg-type]
    start_ts = datetime(2026, 3, 1, tzinfo=timezone.utc)
    end_ts = datetime(2026, 3, 2, tzinfo=timezone.utc)

    context = service.generate_trend_forecast_context(
        start_ts=start_ts,
        end_ts=end_ts,
        timezone="UTC",
        forecast_alpha=0.7,
        trend_epsilon=0.02,
        daily_overview_strategy="strict_daily",
    )

    assert fake.calls[0]["start_ts"] == start_ts
    assert fake.calls[0]["end_ts"] == end_ts
    assert "trend_signals" in context
    assert "forecast_24h" in context
    assert context["data_availability"]["hourly_net_grid_weather"]["count"] == 1


def test_generate_trend_forecast_context_validates_config_params() -> None:
    service = TrendForecastService(
        trino_client=_FakeTrinoClient(
            dataset={"hourly": [], "daily_cost": [], "daily_pv": []}
        )  # type: ignore[arg-type]
    )
    try:
        service.generate_trend_forecast_context(
            start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
            end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
            timezone="UTC",
            forecast_alpha=1.5,
        )
        assert False, "expected ValueError for invalid forecast_alpha"
    except ValueError as error:
        assert "forecast_alpha" in str(error)
