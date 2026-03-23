"""Unit tests for net-grid insight service orchestration."""

from datetime import datetime, timezone

from src.services.net_grid_insight_service import NetGridInsightService


class _FakeTrinoClient:
    def __init__(self, records: list[dict[str, object]]) -> None:
        self.records = records
        self.calls: list[dict[str, object]] = []

    def fetch_net_grid_hourly(
        self,
        start_ts: datetime,
        end_ts: datetime,
        timestamp_column: str,
        metric_columns: list[str],
    ) -> tuple[list[dict[str, object]], str]:
        self.calls.append(
            {
                "start_ts": start_ts,
                "end_ts": end_ts,
                "timestamp_column": timestamp_column,
                "metric_columns": metric_columns,
            }
        )
        return self.records, timestamp_column


def test_generate_outlier_context_handles_empty_window() -> None:
    fake_client = _FakeTrinoClient(records=[])
    service = NetGridInsightService(trino_client=fake_client)  # type: ignore[arg-type]

    context = service.generate_outlier_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        timezone="UTC",
        threshold=3.5,
    )

    assert context["window"]["rows_analyzed"] == 0
    assert context["summary"]["total_outliers"] == 0
    assert context["summary"]["selected_metrics"] == [
        "avg_consumption_kw",
        "avg_generation_kw",
        "estimated_hourly_cost_eur",
    ]
    assert fake_client.calls[0]["timestamp_column"] == "hour"


def test_generate_outlier_context_aggregates_metric_events() -> None:
    records = [
        {"hour": "2026-03-01T00:00:00+00:00", "avg_consumption_kw": 10.0, "avg_generation_kw": 5.0, "estimated_hourly_cost_eur": 1.0},
        {"hour": "2026-03-01T01:00:00+00:00", "avg_consumption_kw": 11.0, "avg_generation_kw": 5.0, "estimated_hourly_cost_eur": 1.0},
        {"hour": "2026-03-01T02:00:00+00:00", "avg_consumption_kw": 10.5, "avg_generation_kw": 5.0, "estimated_hourly_cost_eur": 1.0},
        {"hour": "2026-03-01T03:00:00+00:00", "avg_consumption_kw": 80.0, "avg_generation_kw": 5.0, "estimated_hourly_cost_eur": 1.1},
        {"hour": "2026-03-01T04:00:00+00:00", "avg_consumption_kw": -30.0, "avg_generation_kw": 5.0, "estimated_hourly_cost_eur": 0.9},
    ]
    fake_client = _FakeTrinoClient(records=records)
    service = NetGridInsightService(trino_client=fake_client)  # type: ignore[arg-type]

    context = service.generate_outlier_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        timezone="UTC",
        threshold=3.5,
    )

    assert context["summary"]["total_outliers"] == 2
    assert context["summary"]["outliers_by_metric"] == {"avg_consumption_kw": 2}
    assert {event["event_type"] for event in context["outlier_events"]} == {"spike", "drop"}
