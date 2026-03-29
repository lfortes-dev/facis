"""Integration tests for full AI pipeline with mocked Trino data."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.llm.client import LLMUpstreamError, OpenAICompatibleClient


def _window_payload() -> dict[str, str]:
    return {
        "start_ts": "2026-03-01T00:00:00Z",
        "end_ts": "2026-03-02T00:00:00Z",
        "timezone": "UTC",
    }


def test_anomaly_report_pipeline_e2e(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["insight_type"] == "anomaly-report"
    assert payload["metadata"]["llm_used"] is True
    assert payload["metadata"]["llm_model"] == "gpt-test"
    assert payload["summary"] == "integration-ok"
    assert payload["key_findings"] == ["k1"]
    assert payload["recommendations"] == ["r1"]


def test_anomaly_report_include_data_returns_context(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={**_window_payload(), "robust_z_threshold": 3.5, "include_data": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["data"] is not None
    assert payload["data"]["window"]["rows_analyzed"] >= 1


def test_city_status_pipeline_e2e(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/city-status",
        json=_window_payload(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["insight_type"] == "city-status"
    assert payload["metadata"]["llm_used"] is True
    assert payload["metadata"]["llm_model"] == "gpt-test"
    assert payload["summary"] == "integration-ok"


def test_energy_summary_pipeline_e2e(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/energy-summary",
        json={
            **_window_payload(),
            "forecast_alpha": 0.6,
            "trend_epsilon": 0.02,
            "daily_overview_strategy": "strict_daily",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["insight_type"] == "energy-summary"
    assert payload["metadata"]["llm_used"] is True
    assert payload["metadata"]["llm_model"] == "gpt-test"
    assert payload["summary"] == "integration-ok"


def test_latest_and_output_lookup_work_end_to_end(integration_client: TestClient) -> None:
    created = integration_client.post(
        "/api/v1/insights/city-status",
        json=_window_payload(),
    )
    assert created.status_code == 200
    output_id = created.json()["metadata"]["output_id"]

    latest = integration_client.get("/api/v1/insights/latest")
    assert latest.status_code == 200
    assert latest.json()["latest"]["city-status"]["output"]["metadata"]["output_id"] == output_id

    fetched = integration_client.get(f"/api/ai/outputs/{output_id}")
    assert fetched.status_code == 200
    fetched_payload = fetched.json()
    assert fetched_payload["id"] == output_id
    assert fetched_payload["insight_type"] == "city-status"
    assert fetched_payload["structured_output"]["summary"] == "integration-ok"


def test_output_lookup_returns_404_for_missing_id(integration_client: TestClient) -> None:
    response = integration_client.get("/api/ai/outputs/does-not-exist")
    assert response.status_code == 404


def test_invalid_window_returns_400(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={
            "start_ts": "2026-03-02T00:00:00Z",
            "end_ts": "2026-03-01T00:00:00Z",
            "timezone": "UTC",
            "robust_z_threshold": 3.5,
        },
    )
    assert response.status_code == 400
    assert "earlier" in response.json()["detail"]


def test_invalid_payload_returns_422(integration_client: TestClient) -> None:
    response = integration_client.post(
        "/api/v1/insights/energy-summary",
        json={"start_ts": "2026-03-01T00:00:00Z"},
    )
    assert response.status_code == 422


def test_pipeline_falls_back_when_llm_unavailable(
    integration_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: (_ for _ in ()).throw(LLMUpstreamError("integration llm down")),
    )

    response = integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["llm_used"] is False
    assert payload["metadata"]["llm_model"] == "rule-based-fallback"
    assert payload["metadata"]["llm_error"] == "integration llm down"
    assert "Fallback insight generated from deterministic analytics context" in payload["summary"]


def test_pipeline_falls_back_when_llm_output_is_not_json(
    integration_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: ("plain text output", {"model": "gpt-test"}),
    )
    response = integration_client.post(
        "/api/v1/insights/city-status",
        json=_window_payload(),
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["llm_error"]
    assert "Fallback insight generated from deterministic analytics context" in payload["summary"]


def test_pipeline_falls_back_when_llm_output_schema_is_invalid(
    integration_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: (
            json.dumps({"summary": "only-summary"}),
            {"model": "gpt-test"},
        ),
    )
    response = integration_client.post(
        "/api/v1/insights/energy-summary",
        json={
            **_window_payload(),
            "forecast_alpha": 0.6,
            "trend_epsilon": 0.02,
            "daily_overview_strategy": "strict_daily",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["llm_error"] == "LLM output does not match expected schema"
    assert "Fallback insight generated from deterministic analytics context" in payload["summary"]


def test_pipeline_skips_llm_when_rows_analyzed_is_zero(
    integration_client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("LLM should not be called")),
    )
    monkeypatch.setattr(
        "src.data.trino_client.TrinoQueryClient.fetch_net_grid_hourly",
        lambda self, **kwargs: ([], "hour"),
    )
    response = integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["llm_used"] is False
    assert payload["metadata"]["llm_model"] == "rule-based-fallback"
    assert payload["metadata"]["llm_error"] == "LLM skipped due to insufficient data (rows_analyzed=0)"


def test_policy_requires_headers_when_enabled(
    governed_integration_client: TestClient,
) -> None:
    response = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert response.status_code == 403


def test_policy_requires_role_when_enabled(
    governed_integration_client: TestClient,
) -> None:
    response = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        headers={
            "x-agreement-id": "agreement-1",
            "x-asset-id": "asset-7",
            "x-user-roles": "viewer",
        },
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert response.status_code == 403


def test_rate_limit_returns_429_when_enabled(
    governed_integration_client: TestClient,
    access_headers: dict[str, str],
) -> None:
    first = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        headers=access_headers,
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    second = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        headers=access_headers,
        json={**_window_payload(), "robust_z_threshold": 3.5},
    )
    assert first.status_code == 200
    assert second.status_code == 429
    assert "retry-after" in second.headers


def test_dev_mode_hides_llm_error_for_successful_llm_response(
    integration_client: TestClient,
) -> None:
    response = integration_client.post(
        "/api/v1/insights/city-status",
        json=_window_payload(),
    )
    assert response.status_code == 200
    assert response.json()["metadata"]["llm_error"] is None


def test_latest_endpoint_empty_before_any_insight(
    integration_client: TestClient,
) -> None:
    response = integration_client.get("/api/v1/insights/latest")
    assert response.status_code == 200
    latest = response.json()["latest"]
    assert latest["anomaly-report"] is None
    assert latest["city-status"] is None
    assert latest["energy-summary"] is None
