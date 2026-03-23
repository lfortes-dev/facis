"""Unit tests for Smart City hybrid correlation analytics and context builder."""

from datetime import datetime, timezone

from src.analytics.smart_city_correlation import (
    CorrelationResult,
    analyze_event_infrastructure_correlation,
)
from src.llm.context_builder import build_smart_city_correlation_context


def test_analyze_event_infrastructure_correlation_detects_high_confidence_pattern() -> None:
    rows = []
    for hour in range(24):
        rows.append(
            {
                "event_date": "2026-03-01",
                "zone_id": "zone-a",
                "event_type": "festival",
                "event_count": 1,
                "avg_severity": 1.0,
                "active_count": 0,
                "hour": f"2026-03-01T{hour:02d}:00:00+00:00",
                "avg_dimming_pct": 30.0 + ((hour % 3) - 1),
                "total_power_w": 50.0 + ((hour % 4) - 2),
                "light_count": 24,
            }
        )
    for hour in range(4):
        rows.append(
            {
                "event_date": "2026-03-02",
                "zone_id": "zone-a",
                "event_type": "accident",
                "event_count": 3,
                "avg_severity": 3.0,
                "active_count": 3,
                "hour": f"2026-03-02T{hour:02d}:00:00+00:00",
                "avg_dimming_pct": 95.0,
                "total_power_w": 320.0,
                "light_count": 24,
            }
        )

    result = analyze_event_infrastructure_correlation(rows)

    assert len(result.event_response_patterns) == 2
    assert result.lag_distribution == {"0-6h": 10, "6-24h": 18, "24-48h": 0}
    assert len(result.high_confidence_links) == 1
    assert result.high_confidence_links[0]["event_type"] == "accident"
    zone_a = next(item for item in result.zone_response_summary if item["zone_id"] == "zone-a")
    assert zone_a["patterns"] == 2


def test_build_smart_city_correlation_context_has_stable_shape() -> None:
    result = CorrelationResult(
        event_response_patterns=[
            {
                "event_date": "2026-03-02",
                "zone_id": "zone-a",
                "event_type": "accident",
                "response_score": 0.83,
                "confidence": "high",
            }
        ],
        lag_distribution={"0-6h": 3, "6-24h": 9, "24-48h": 0},
        zone_response_summary=[
            {
                "zone_id": "zone-a",
                "patterns": 1,
                "high_confidence_patterns": 1,
                "avg_response_score": 0.83,
            }
        ],
        high_confidence_links=[
            {
                "event_date": "2026-03-02",
                "zone_id": "zone-a",
                "event_type": "accident",
                "response_score": 0.83,
            }
        ],
    )
    context = build_smart_city_correlation_context(
        start_ts=datetime(2026, 3, 1, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 3, tzinfo=timezone.utc),
        timezone="UTC",
        total_rows=12,
        correlation_result=result,
    )

    assert context["window"]["rows_analyzed"] == 12
    assert context["summary"]["total_patterns"] == 1
    assert context["summary"]["high_confidence_links"] == 1
    assert context["summary"]["confidence_distribution"]["high"] == 1
    assert context["lag_distribution"]["24-48h"] == 0
