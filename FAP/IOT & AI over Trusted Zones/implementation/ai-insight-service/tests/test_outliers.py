"""Unit tests for robust outlier detection."""

from src.analytics.outliers import detect_metric_outliers


def test_detect_metric_outliers_flags_spike_and_drop() -> None:
    records = [
        {"ts": "2026-01-01T00:00:00", "consumption_kwh": 10.0},
        {"ts": "2026-01-01T01:00:00", "consumption_kwh": 11.0},
        {"ts": "2026-01-01T02:00:00", "consumption_kwh": 10.5},
        {"ts": "2026-01-01T03:00:00", "consumption_kwh": 80.0},
        {"ts": "2026-01-01T04:00:00", "consumption_kwh": -30.0},
    ]

    events, summary = detect_metric_outliers(
        records=records,
        metric="consumption_kwh",
        timestamp_column="ts",
        threshold=3.5,
    )

    assert summary is not None
    assert len(events) == 2
    assert {event["event_type"] for event in events} == {"spike", "drop"}
