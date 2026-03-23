"""API tests for insights and health endpoints."""

from datetime import datetime

from requests import exceptions as requests_exceptions

from src.api.rest.routes import insights


def test_health_endpoint(client) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_outlier_endpoint_returns_context(client, monkeypatch) -> None:
    class FakeService:
        def generate_outlier_context(
            self,
            *,
            start_ts: datetime,
            end_ts: datetime,
            timezone: str,
            threshold: float,
        ):
            assert start_ts < end_ts
            assert timezone == "UTC"
            assert threshold == 3.5
            return {
                "window": {
                    "start_ts": start_ts.isoformat(),
                    "end_ts": end_ts.isoformat(),
                    "timezone": timezone,
                    "rows_analyzed": 0,
                },
                "baseline_stats": [],
                "outlier_events": [],
                "cost_anomalies": [],
                "narrative_hints": [
                    "No robust outliers detected for the selected metrics and window."
                ],
                "summary": {"total_outliers": 0, "outliers_by_metric": {}, "selected_metrics": []},
            }

    monkeypatch.setattr(insights, "get_insight_service", lambda: FakeService())
    response = client.post(
        "/api/v1/insights/net-grid/outliers",
        json={
            "start_ts": "2026-01-01T00:00:00Z",
            "end_ts": "2026-01-02T00:00:00Z",
            "timezone": "UTC",
            "robust_z_threshold": 3.5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "context" in payload
    assert payload["context"]["summary"]["total_outliers"] == 0


def test_smart_city_correlation_endpoint_returns_context(client, monkeypatch) -> None:
    class FakeSmartCityService:
        def generate_correlation_context(
            self,
            *,
            start_ts: datetime,
            end_ts: datetime,
            timezone: str,
        ):
            assert start_ts < end_ts
            assert timezone == "UTC"
            return {
                "window": {
                    "start_ts": start_ts.isoformat(),
                    "end_ts": end_ts.isoformat(),
                    "timezone": timezone,
                    "rows_analyzed": 10,
                },
                "event_response_patterns": [],
                "lag_distribution": {"0-6h": 0, "6-24h": 0, "24-48h": 0},
                "zone_response_summary": [],
                "high_confidence_links": [],
                "narrative_hints": [],
                "summary": {
                    "total_patterns": 0,
                    "high_confidence_links": 0,
                    "confidence_distribution": {"high": 0, "medium": 0, "low": 0},
                },
            }

    monkeypatch.setattr(
        insights,
        "get_smart_city_correlation_service",
        lambda: FakeSmartCityService(),
    )
    response = client.post(
        "/api/v1/insights/smart-city/correlation",
        json={
            "start_ts": "2026-01-01T00:00:00Z",
            "end_ts": "2026-01-02T00:00:00Z",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "context" in payload
    assert payload["context"]["summary"]["total_patterns"] == 0


def test_smart_city_correlation_endpoint_rejects_invalid_range(client, monkeypatch) -> None:
    class FakeSmartCityService:
        def generate_correlation_context(self, **kwargs):
            raise ValueError("start_ts must be earlier than end_ts")

    monkeypatch.setattr(
        insights,
        "get_smart_city_correlation_service",
        lambda: FakeSmartCityService(),
    )
    response = client.post(
        "/api/v1/insights/smart-city/correlation",
        json={
            "start_ts": "2026-01-02T00:00:00Z",
            "end_ts": "2026-01-01T00:00:00Z",
            "timezone": "UTC",
        },
    )

    assert response.status_code == 400
    assert "earlier" in response.json()["detail"]


def test_outlier_endpoint_rejects_invalid_range(client, monkeypatch) -> None:
    class FakeService:
        def generate_outlier_context(self, **kwargs):
            raise ValueError("start_ts must be earlier than end_ts")

    monkeypatch.setattr(insights, "get_insight_service", lambda: FakeService())
    response = client.post(
        "/api/v1/insights/net-grid/outliers",
        json={
            "start_ts": "2026-01-02T00:00:00Z",
            "end_ts": "2026-01-01T00:00:00Z",
            "timezone": "UTC",
            "robust_z_threshold": 3.5,
        },
    )

    assert response.status_code == 400
    assert "earlier" in response.json()["detail"]


def test_outlier_endpoint_sanitizes_timeout_error(client, monkeypatch) -> None:
    class FakeService:
        def generate_outlier_context(self, **kwargs):
            raise requests_exceptions.ConnectTimeout("raw internal timeout details")

    monkeypatch.setattr(insights, "get_insight_service", lambda: FakeService())
    response = client.post(
        "/api/v1/insights/net-grid/outliers",
        json={
            "start_ts": "2026-01-01T00:00:00Z",
            "end_ts": "2026-01-02T00:00:00Z",
            "timezone": "UTC",
            "robust_z_threshold": 3.5,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream Trino request timed out"


def test_outlier_endpoint_sanitizes_unexpected_error(client, monkeypatch) -> None:
    class FakeService:
        def generate_outlier_context(self, **kwargs):
            raise RuntimeError("secret stack trace text")

    monkeypatch.setattr(insights, "get_insight_service", lambda: FakeService())
    response = client.post(
        "/api/v1/insights/net-grid/outliers",
        json={
            "start_ts": "2026-01-01T00:00:00Z",
            "end_ts": "2026-01-02T00:00:00Z",
            "timezone": "UTC",
            "robust_z_threshold": 3.5,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream dependency failure while generating insight"


def test_openapi_json_available(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    payload = response.json()
    assert payload["openapi"] == "3.0.3"
    assert payload["info"]["title"] == "FACIS AI Insight Service"
    assert "/api/v1/insights/net-grid/outliers" in payload["paths"]
    assert "/api/v1/insights/smart-city/correlation" in payload["paths"]
    smart_city_description = payload["paths"]["/api/v1/insights/smart-city/correlation"]["post"]["description"]
    assert "MAD = median(|x_i - median(x)|)" in smart_city_description
    assert "response_score =" in smart_city_description


def test_docs_available(client) -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger" in response.text.lower() or "openapi" in response.text.lower()


def test_redoc_available(client) -> None:
    response = client.get("/redoc")
    assert response.status_code == 200
