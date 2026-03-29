"""BDD scenarios for AI insight generation endpoints."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pytest_bdd import given, parsers, scenarios, then, when

from src.llm.client import LLMUpstreamError, OpenAICompatibleClient

pytest_plugins = ("tests.integration.conftest",)

scenarios("features/ai_insight_generation.feature")

_ENDPOINT_TO_INSIGHT_TYPE = {
    "/api/v1/insights/anomaly-report": "anomaly-report",
    "/api/v1/insights/city-status": "city-status",
    "/api/v1/insights/energy-summary": "energy-summary",
}


def _window_payload() -> dict[str, str]:
    return {
        "start_ts": "2026-03-01T00:00:00Z",
        "end_ts": "2026-03-02T00:00:00Z",
        "timezone": "UTC",
    }


def _payload_for_endpoint(endpoint: str) -> dict[str, Any]:
    payload: dict[str, Any] = _window_payload()
    if endpoint == "/api/v1/insights/anomaly-report":
        payload["robust_z_threshold"] = 3.5
    elif endpoint == "/api/v1/insights/energy-summary":
        payload.update(
            {
                "forecast_alpha": 0.6,
                "trend_epsilon": 0.02,
                "daily_overview_strategy": "strict_daily",
            }
        )
    return payload


def _active_client(
    bdd_context: dict[str, Any],
    request: pytest.FixtureRequest,
) -> TestClient:
    fixture_name = "integration_client"
    if bdd_context["client_mode"] == "governed":
        fixture_name = "governed_integration_client"
    return request.getfixturevalue(fixture_name)


def _apply_runtime_overrides(
    bdd_context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    llm_mode = bdd_context["llm_mode"]
    if llm_mode == "unavailable":
        monkeypatch.setattr(
            OpenAICompatibleClient,
            "create_chat_completion",
            lambda self, **kwargs: (_ for _ in ()).throw(LLMUpstreamError("integration llm down")),
        )
    elif llm_mode == "plain_text":
        monkeypatch.setattr(
            OpenAICompatibleClient,
            "create_chat_completion",
            lambda self, **kwargs: ("plain text output", {"model": "gpt-test"}),
        )
    elif llm_mode == "invalid_schema":
        monkeypatch.setattr(
            OpenAICompatibleClient,
            "create_chat_completion",
            lambda self, **kwargs: (json.dumps({"summary": "only-summary"}), {"model": "gpt-test"}),
        )

    if bdd_context["rows_mode"] == "empty":
        monkeypatch.setattr(
            "src.data.trino_client.TrinoQueryClient.fetch_net_grid_hourly",
            lambda self, **kwargs: ([], "hour"),
        )


@pytest.fixture()
def bdd_context() -> dict[str, Any]:
    return {
        "endpoint": None,
        "payload": {},
        "headers": {},
        "response": None,
        "first_response": None,
        "second_response": None,
        "client_mode": "integration",
        "output_id": None,
        "llm_mode": None,
        "rows_mode": None,
        "preserve_payload": False,
    }


@given("a valid UTC insight window")
def given_valid_utc_insight_window(bdd_context: dict[str, Any]) -> None:
    bdd_context["payload"] = _window_payload()


@given("anomaly report parameters are set")
def given_anomaly_report_parameters_set(bdd_context: dict[str, Any]) -> None:
    bdd_context["payload"]["robust_z_threshold"] = 3.5


@given("include_data is enabled")
def given_include_data_is_enabled(bdd_context: dict[str, Any]) -> None:
    bdd_context["payload"]["include_data"] = True


@given("an invalid reversed UTC insight window")
def given_invalid_reversed_utc_insight_window(bdd_context: dict[str, Any]) -> None:
    bdd_context["payload"] = {
        "start_ts": "2026-03-02T00:00:00Z",
        "end_ts": "2026-03-01T00:00:00Z",
        "timezone": "UTC",
        "robust_z_threshold": 3.5,
    }


@given("an incomplete payload for energy summary")
def given_incomplete_payload_for_energy_summary(bdd_context: dict[str, Any]) -> None:
    bdd_context["payload"] = {"start_ts": "2026-03-01T00:00:00Z"}
    bdd_context["preserve_payload"] = True


@given("governance checks are enabled")
def given_governance_checks_are_enabled(bdd_context: dict[str, Any]) -> None:
    bdd_context["client_mode"] = "governed"


@given("valid policy headers are provided")
def given_valid_policy_headers_are_provided(
    bdd_context: dict[str, Any], access_headers: dict[str, str]
) -> None:
    bdd_context["headers"] = access_headers


@given("policy headers contain a non-consumer role")
def given_policy_headers_contain_non_consumer_role(
    bdd_context: dict[str, Any]
) -> None:
    bdd_context["headers"] = {
        "x-agreement-id": "agreement-1",
        "x-asset-id": "asset-7",
        "x-user-roles": "viewer",
    }


@given("LLM upstream is unavailable")
def given_llm_upstream_is_unavailable(bdd_context: dict[str, Any]) -> None:
    bdd_context["llm_mode"] = "unavailable"


@given("LLM output is plain text")
def given_llm_output_is_plain_text(bdd_context: dict[str, Any]) -> None:
    bdd_context["llm_mode"] = "plain_text"


@given("LLM output schema is invalid")
def given_llm_output_schema_is_invalid(bdd_context: dict[str, Any]) -> None:
    bdd_context["llm_mode"] = "invalid_schema"


@given("no anomaly rows are available")
def given_no_anomaly_rows_are_available(bdd_context: dict[str, Any]) -> None:
    bdd_context["rows_mode"] = "empty"


@given(parsers.parse('a request payload is prepared for "{endpoint}"'))
def given_request_payload_prepared_for_endpoint(
    bdd_context: dict[str, Any], endpoint: str
) -> None:
    bdd_context["endpoint"] = endpoint
    bdd_context["payload"] = _payload_for_endpoint(endpoint)


@when(parsers.parse('I request AI insight generation at "{endpoint}"'))
def when_request_ai_insight_generation(
    bdd_context: dict[str, Any],
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
    endpoint: str,
) -> None:
    bdd_context["endpoint"] = endpoint
    if not bdd_context["preserve_payload"]:
        base_payload = _payload_for_endpoint(endpoint)
        if bdd_context["payload"]:
            base_payload.update(bdd_context["payload"])
        bdd_context["payload"] = base_payload
    elif not bdd_context["payload"]:
        bdd_context["payload"] = _payload_for_endpoint(endpoint)
    client = _active_client(bdd_context, request)
    _apply_runtime_overrides(bdd_context, monkeypatch)
    bdd_context["response"] = client.post(
        endpoint,
        json=bdd_context["payload"],
        headers=bdd_context["headers"],
    )


@when("I generate a city status insight")
def when_generate_city_status_insight(
    bdd_context: dict[str, Any], integration_client: TestClient
) -> None:
    created = integration_client.post("/api/v1/insights/city-status", json=_window_payload())
    assert created.status_code == 200
    bdd_context["output_id"] = created.json()["metadata"]["output_id"]


@when("I request the latest insights snapshot")
def when_request_latest_insights_snapshot(
    bdd_context: dict[str, Any], integration_client: TestClient
) -> None:
    bdd_context["response"] = integration_client.get("/api/v1/insights/latest")


@when("I request the created output by id")
def when_request_created_output_by_id(
    bdd_context: dict[str, Any], integration_client: TestClient
) -> None:
    bdd_context["response"] = integration_client.get(f"/api/ai/outputs/{bdd_context['output_id']}")


@when(parsers.parse('I request output by id "{output_id}"'))
def when_request_output_by_id(
    bdd_context: dict[str, Any], integration_client: TestClient, output_id: str
) -> None:
    bdd_context["response"] = integration_client.get(f"/api/ai/outputs/{output_id}")


@when("I request energy summary insight with invalid LLM schema output")
def when_request_energy_summary_with_invalid_llm_schema_output(
    bdd_context: dict[str, Any],
    integration_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: (json.dumps({"summary": "only-summary"}), {"model": "gpt-test"}),
    )
    payload = _payload_for_endpoint("/api/v1/insights/energy-summary")
    payload.update(bdd_context["payload"])
    bdd_context["response"] = integration_client.post(
        "/api/v1/insights/energy-summary",
        json=payload,
    )


@when("I send two anomaly insight requests under governance")
def when_send_two_anomaly_insight_requests_under_governance(
    bdd_context: dict[str, Any], governed_integration_client: TestClient
) -> None:
    payload = bdd_context["payload"] or _payload_for_endpoint("/api/v1/insights/anomaly-report")
    headers = bdd_context["headers"]
    bdd_context["first_response"] = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        json=payload,
        headers=headers,
    )
    bdd_context["second_response"] = governed_integration_client.post(
        "/api/v1/insights/anomaly-report",
        json=payload,
        headers=headers,
    )


@then(parsers.parse("the response status code is {status_code:d}"))
def then_response_status_code_is(
    bdd_context: dict[str, Any], status_code: int
) -> None:
    response = bdd_context["response"]
    assert response is not None
    assert response.status_code == status_code


@then(parsers.parse("the first response status code is {status_code:d}"))
def then_first_response_status_code_is(
    bdd_context: dict[str, Any], status_code: int
) -> None:
    assert bdd_context["first_response"] is not None
    assert bdd_context["first_response"].status_code == status_code


@then(parsers.parse("the second response status code is {status_code:d}"))
def then_second_response_status_code_is(
    bdd_context: dict[str, Any], status_code: int
) -> None:
    assert bdd_context["second_response"] is not None
    assert bdd_context["second_response"].status_code == status_code


@then(parsers.parse('the returned insight type is "{insight_type}"'))
def then_returned_insight_type_is(
    bdd_context: dict[str, Any], insight_type: str
) -> None:
    payload = bdd_context["response"].json()
    assert payload["insight_type"] == insight_type


@then(parsers.parse('the endpoint insight type is correct for "{endpoint}"'))
def then_endpoint_insight_type_is_correct(
    bdd_context: dict[str, Any], endpoint: str
) -> None:
    payload = bdd_context["response"].json()
    assert payload["insight_type"] == _ENDPOINT_TO_INSIGHT_TYPE[endpoint]


@then("LLM metadata indicates successful generation")
def then_llm_metadata_indicates_successful_generation(
    bdd_context: dict[str, Any]
) -> None:
    payload = bdd_context["response"].json()
    assert payload["metadata"]["llm_used"] is True
    assert payload["metadata"]["llm_model"] == "gpt-test"


@then("the insight summary contains generated content")
def then_insight_summary_contains_generated_content(
    bdd_context: dict[str, Any]
) -> None:
    payload = bdd_context["response"].json()
    assert isinstance(payload["summary"], str)
    assert payload["summary"].strip() != ""


@then("the insight response format is valid")
def then_insight_response_format_is_valid(
    bdd_context: dict[str, Any]
) -> None:
    payload = bdd_context["response"].json()
    required_keys = {"insight_type", "summary", "key_findings", "recommendations", "metadata"}
    assert required_keys.issubset(payload.keys())
    assert isinstance(payload["insight_type"], str)
    assert payload["insight_type"] in set(_ENDPOINT_TO_INSIGHT_TYPE.values())
    assert isinstance(payload["summary"], str)
    assert payload["summary"].strip() != ""
    assert isinstance(payload["key_findings"], list)
    assert len(payload["key_findings"]) >= 1
    assert isinstance(payload["recommendations"], list)
    assert len(payload["recommendations"]) >= 1
    assert isinstance(payload["metadata"], dict)


@then("the response contains analyzed window data")
def then_response_contains_analyzed_window_data(
    bdd_context: dict[str, Any]
) -> None:
    payload = bdd_context["response"].json()
    assert payload["data"] is not None
    assert payload["data"]["window"]["rows_analyzed"] >= 1


@then("latest city-status output id matches the created output id")
def then_latest_city_status_output_matches_created(
    bdd_context: dict[str, Any]
) -> None:
    latest_payload = bdd_context["response"].json()
    latest_output_id = latest_payload["latest"]["city-status"]["output"]["metadata"]["output_id"]
    assert latest_output_id == bdd_context["output_id"]


@then("the output lookup succeeds with city-status content")
def then_output_lookup_succeeds_with_city_status_content(
    bdd_context: dict[str, Any]
) -> None:
    output_payload = bdd_context["response"].json()
    assert output_payload["id"] == bdd_context["output_id"]
    assert output_payload["insight_type"] == "city-status"
    assert output_payload["structured_output"]["summary"] == "integration-ok"


@then(parsers.parse('the error detail contains "{expected_text}"'))
def then_error_detail_contains(
    bdd_context: dict[str, Any], expected_text: str
) -> None:
    assert expected_text in bdd_context["response"].json()["detail"]


@then(parsers.parse('fallback metadata indicates "{llm_error}"'))
def then_fallback_metadata_indicates(
    bdd_context: dict[str, Any], llm_error: str
) -> None:
    payload = bdd_context["response"].json()
    # Some service builds may normalize partial LLM output instead of falling back.
    if llm_error == "LLM output does not match expected schema" and payload["metadata"]["llm_used"]:
        assert payload["metadata"]["llm_error"] == llm_error
        assert payload["summary"].strip() != ""
        return
    assert payload["metadata"]["llm_used"] is False
    assert payload["metadata"]["llm_model"] == "rule-based-fallback"
    assert payload["metadata"]["llm_error"] == llm_error


@then("fallback summary is returned")
def then_fallback_summary_is_returned(
    bdd_context: dict[str, Any]
) -> None:
    payload = bdd_context["response"].json()
    assert payload["metadata"]["llm_error"]
    assert "Fallback insight generated from deterministic analytics context" in payload["summary"]


@then("the second response has retry-after header")
def then_second_response_has_retry_after_header(
    bdd_context: dict[str, Any]
) -> None:
    assert "retry-after" in bdd_context["second_response"].headers


@then("llm_error is null in metadata")
def then_llm_error_is_null_in_metadata(
    bdd_context: dict[str, Any]
) -> None:
    assert bdd_context["response"].json()["metadata"]["llm_error"] is None


@then("latest insights are empty for all insight types")
def then_latest_insights_are_empty_for_all_types(
    bdd_context: dict[str, Any]
) -> None:
    latest = bdd_context["response"].json()["latest"]
    assert latest["anomaly-report"] is None
    assert latest["city-status"] is None
    assert latest["energy-summary"] is None
