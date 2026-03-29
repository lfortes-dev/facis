"""Tests for LLM prompt template rendering."""

from __future__ import annotations

from pathlib import Path

import src.llm.prompt_templates as prompt_templates
from src.llm.prompt_templates import (
    EXPECTED_OUTPUT_JSON_SCHEMA,
    build_prompt_payload,
    build_system_prompt,
    build_user_prompt,
)


def test_system_prompt_contains_required_sections() -> None:
    prompt = build_system_prompt(insight_type="net_grid_outliers")
    assert "simulation-service" in prompt
    assert "Data schema guide:" in prompt
    assert "Return ONLY valid JSON" in prompt
    assert "summary" in prompt
    assert "key_findings" in prompt
    assert "recommendations" in prompt


def test_user_prompt_is_deterministic_for_same_context() -> None:
    context = {
        "window": {
            "start_ts": "2026-03-01T00:00:00+00:00",
            "end_ts": "2026-03-02T00:00:00+00:00",
            "timezone": "UTC",
            "rows_analyzed": 24,
        },
        "summary": {"total_outliers": 1, "outliers_by_metric": {"grid_cost": 1}},
    }
    first_prompt = build_user_prompt(context=context)
    second_prompt = build_user_prompt(context=context)
    assert first_prompt == second_prompt


def test_prompt_payload_has_expected_schema_and_keys() -> None:
    payload = build_prompt_payload(
        insight_type="smart_city_correlation",
        context={"summary": {"total_patterns": 2}},
    )
    assert set(payload.keys()) == {"system", "user", "expected_json_schema"}
    assert payload["expected_json_schema"] == EXPECTED_OUTPUT_JSON_SCHEMA
    assert payload["expected_json_schema"]["required"] == [
        "summary",
        "key_findings",
        "recommendations",
    ]
    assert payload["expected_json_schema"]["additionalProperties"] is False


def test_prompt_payload_renders_all_supported_insight_types() -> None:
    for insight_type in (
        "net_grid_outliers",
        "smart_city_correlation",
        "energy_trend_forecast",
    ):
        payload = build_prompt_payload(insight_type=insight_type, context={"summary": {}})
        assert "Insight type:" in payload["system"]
        assert "Context JSON:" in payload["user"]


def test_prompt_templates_can_be_overridden_from_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AI_INSIGHT_PROMPT_TEMPLATES__ENABLED", "true")
    monkeypatch.setenv("AI_INSIGHT_PROMPT_TEMPLATES__PATH", str(tmp_path))
    (tmp_path / "simulation_service_context.txt").write_text(
        "CUSTOM_SIM_CONTEXT",
        encoding="utf-8",
    )
    (tmp_path / "insight_type_net_grid_outliers.txt").write_text(
        "CUSTOM_INSIGHT_DESCRIPTION",
        encoding="utf-8",
    )

    prompt_templates._load_prompt_template_overrides.cache_clear()
    prompt = build_system_prompt(insight_type="net_grid_outliers")

    assert "CUSTOM_SIM_CONTEXT" in prompt
    assert "CUSTOM_INSIGHT_DESCRIPTION" in prompt
    assert "Data schema guide:" in prompt


def test_prompt_templates_fall_back_when_override_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_INSIGHT_PROMPT_TEMPLATES__ENABLED", "false")
    prompt_templates._load_prompt_template_overrides.cache_clear()

    prompt = build_system_prompt(insight_type="net_grid_outliers")

    assert "FACIS domain context:" in prompt
