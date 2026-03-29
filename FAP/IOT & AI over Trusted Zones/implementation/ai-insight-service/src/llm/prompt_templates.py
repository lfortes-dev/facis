"""Prompt engineering templates for deterministic insight narration."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, TypedDict

from src.config import load_config

InsightType = Literal["net_grid_outliers", "smart_city_correlation", "energy_trend_forecast"]


class PromptPayload(TypedDict):
    """Structured prompt payload for downstream LLM clients."""

    system: str
    user: str
    expected_json_schema: dict[str, Any]


SIMULATION_SERVICE_CONTEXT = (
    "FACIS domain context:\n"
    "- This analysis supports the FACIS demonstrator where simulation-service "
    "generates IoT/Smart-City "
    "events and related telemetry that are later analyzed in ai-insight-service.\n"
    "- Consider data provenance as simulation-backed unless a field indicates otherwise.\n"
    "- Keep claims aligned with provided context only; "
    "do not invent missing measurements or causes."
)

DATA_SCHEMA_DESCRIPTIONS = (
    "Data schema guide:\n"
    "- `window`: `{start_ts, end_ts, timezone, rows_analyzed}` for analysis scope.\n"
    "- `summary`: compact metrics for quick interpretation.\n"
    "- `narrative_hints`: deterministic cues from analytics logic; "
    "treat as guidance, not hard facts.\n"
    "- Outlier context includes `baseline_stats`, `outlier_events`, and `cost_anomalies`.\n"
    "- Smart-city context includes `event_response_patterns`, `lag_distribution`, and "
    "`high_confidence_links`.\n"
    "- Trend/forecast context includes `trend_signals`, `moving_averages`, `seasonality_patterns`, "
    "`forecast_24h`, and `data_availability`."
)

OUTPUT_FORMAT_INSTRUCTIONS = (
    "Return ONLY valid JSON, with no markdown and no prose outside JSON.\n"
    "Required top-level object keys (exactly these keys):\n"
    "- `summary`: string (2-4 sentences, concise executive overview)\n"
    "- `key_findings`: array of strings (3-6 bullets worth of findings, each one sentence)\n"
    "- `recommendations`: array of strings (2-5 actionable recommendations, each one sentence)\n"
    "Constraints:\n"
    "- Do not include additional top-level keys.\n"
    "- Preserve factual consistency with provided context.\n"
    "- If evidence is insufficient, state uncertainty explicitly in findings/recommendations."
)

INSIGHT_TYPE_DESCRIPTIONS: dict[InsightType, str] = {
    "net_grid_outliers": (
        "Insight type: Net-grid outlier analysis.\n"
        "Focus on abnormal consumption/generation/cost behavior, "
        "frequency by metric, and likely impact."
    ),
    "smart_city_correlation": (
        "Insight type: Smart-city event correlation.\n"
        "Focus on event-to-infrastructure response, confidence levels, "
        "lag windows, and zone patterns."
    ),
    "energy_trend_forecast": (
        "Insight type: Energy trend and 24h forecast.\n"
        "Focus on trend direction, seasonality effects, forecast plausibility, "
        "and operational implications."
    ),
}

EXPECTED_OUTPUT_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "key_findings", "recommendations"],
    "properties": {
        "summary": {"type": "string"},
        "key_findings": {"type": "array", "items": {"type": "string"}},
        "recommendations": {"type": "array", "items": {"type": "string"}},
    },
}

_OVERRIDE_FILES = {
    "simulation_service_context": "simulation_service_context.txt",
    "data_schema_descriptions": "data_schema_descriptions.txt",
    "output_format_instructions": "output_format_instructions.txt",
    "insight_type:net_grid_outliers": "insight_type_net_grid_outliers.txt",
    "insight_type:smart_city_correlation": "insight_type_smart_city_correlation.txt",
    "insight_type:energy_trend_forecast": "insight_type_energy_trend_forecast.txt",
}


@lru_cache(maxsize=1)
def _load_prompt_template_overrides() -> dict[str, str]:
    """Load optional prompt template overrides from configured path."""
    settings = load_config()
    if not settings.prompt_templates.enabled:
        return {}

    base_path = Path(settings.prompt_templates.path)
    if not base_path.exists() or not base_path.is_dir():
        return {}

    overrides: dict[str, str] = {}
    for key, filename in _OVERRIDE_FILES.items():
        path = base_path / filename
        if not path.exists() or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").strip()
        if text:
            overrides[key] = text
    return overrides


def build_system_prompt(*, insight_type: InsightType) -> str:
    """Build the shared system prompt with static context and constraints."""
    overrides = _load_prompt_template_overrides()
    insight_description = overrides.get(
        f"insight_type:{insight_type}",
        INSIGHT_TYPE_DESCRIPTIONS[insight_type],
    )
    simulation_service_context = overrides.get(
        "simulation_service_context",
        SIMULATION_SERVICE_CONTEXT,
    )
    data_schema_descriptions = overrides.get(
        "data_schema_descriptions",
        DATA_SCHEMA_DESCRIPTIONS,
    )
    output_format_instructions = overrides.get(
        "output_format_instructions",
        OUTPUT_FORMAT_INSTRUCTIONS,
    )
    return "\n\n".join(
        [
            "You are an energy and smart-city analytics assistant.",
            insight_description,
            simulation_service_context,
            data_schema_descriptions,
            output_format_instructions,
        ]
    )


def build_user_prompt(*, context: dict[str, Any]) -> str:
    """Build deterministic user prompt with compact JSON context."""
    context_json = json.dumps(context, ensure_ascii=True, sort_keys=True, indent=2, default=str)
    return (
        "Analyze the following structured context and produce the required JSON output.\n"
        "Context JSON:\n"
        f"{context_json}"
    )


def build_prompt_payload(*, insight_type: InsightType, context: dict[str, Any]) -> PromptPayload:
    """Create a structured prompt payload for LLM client consumption."""
    return {
        "system": build_system_prompt(insight_type=insight_type),
        "user": build_user_prompt(context=context),
        "expected_json_schema": EXPECTED_OUTPUT_JSON_SCHEMA,
    }
