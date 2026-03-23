"""Unit tests for Smart City correlation service orchestration."""

from datetime import datetime, timezone

from src.services.smart_city_correlation_service import SmartCityCorrelationService


class _FakeTrinoClient:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.calls: list[dict[str, datetime]] = []

    def fetch_smart_city_correlation_rows(
        self,
        start_ts: datetime,
        end_ts: datetime,
    ) -> list[dict[str, object]]:
        self.calls.append({"start_ts": start_ts, "end_ts": end_ts})
        return self.rows


def test_generate_correlation_context_handles_empty_rows() -> None:
    service = SmartCityCorrelationService(
        trino_client=_FakeTrinoClient(rows=[])  # type: ignore[arg-type]
    )
    context = service.generate_correlation_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
        timezone="UTC",
    )

    assert context["window"]["rows_analyzed"] == 0
    assert context["summary"]["total_patterns"] == 0
    assert context["summary"]["high_confidence_links"] == 0


def test_generate_correlation_context_validates_time_window() -> None:
    service = SmartCityCorrelationService(
        trino_client=_FakeTrinoClient(rows=[])  # type: ignore[arg-type]
    )

    try:
        service.generate_correlation_context(
            start_ts=datetime(2026, 3, 2, tzinfo=timezone.utc),
            end_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
            timezone="UTC",
        )
        assert False, "expected ValueError for invalid time window"
    except ValueError as error:
        assert "earlier" in str(error)


def test_generate_correlation_context_invokes_trino_with_bounds() -> None:
    fake = _FakeTrinoClient(
        rows=[
            {
                "event_date": "2026-03-02",
                "zone_id": "zone-a",
                "event_type": "accident",
                "event_count": 2,
                "avg_severity": 2.5,
                "active_count": 1,
                "hour": "2026-03-02T01:00:00+00:00",
                "avg_dimming_pct": 82.0,
                "total_power_w": 250.0,
                "light_count": 20,
            }
        ]
    )
    service = SmartCityCorrelationService(trino_client=fake)  # type: ignore[arg-type]
    start_ts = datetime(2026, 3, 2, tzinfo=timezone.utc)
    end_ts = datetime(2026, 3, 3, tzinfo=timezone.utc)

    context = service.generate_correlation_context(
        start_ts=start_ts,
        end_ts=end_ts,
        timezone="UTC",
    )

    assert fake.calls[0]["start_ts"] == start_ts
    assert fake.calls[0]["end_ts"] == end_ts
    assert context["summary"]["total_patterns"] == 1
    assert context["event_response_patterns"][0]["zone_id"] == "zone-a"
