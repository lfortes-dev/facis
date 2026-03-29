"""End-to-end orchestration for governed AI insight generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from src.llm import build_prompt_payload
from src.llm.client import (
    LLMClientError,
    LLMRateLimitError,
    LLMUpstreamError,
    OpenAICompatibleClient,
)
from src.observability.audit_log import AuditLogger
from src.services.net_grid_insight_service import NetGridInsightService
from src.services.smart_city_correlation_service import SmartCityCorrelationService
from src.services.trend_forecast_service import TrendForecastService
from src.storage.output_store import AIOutputRecord, InMemoryOutputStore

PromptInsightType = Literal["net_grid_outliers", "smart_city_correlation", "energy_trend_forecast"]

_PII_KEY_HINTS = ("name", "email", "phone", "address", "ssn")


@dataclass(frozen=True)
class InsightExecutionResult:
    """Container for orchestration result."""

    record: AIOutputRecord
    context: dict[str, Any]
    llm_used: bool
    openai_error: str | None = None


class InsightOrchestrator:
    """Build context, call LLM, fallback safely, and persist results."""

    def __init__(
        self,
        *,
        outlier_service: NetGridInsightService,
        smart_city_service: SmartCityCorrelationService,
        trend_service: TrendForecastService,
        llm_client: OpenAICompatibleClient,
        output_store: InMemoryOutputStore,
        audit_logger: AuditLogger,
    ) -> None:
        self._outlier_service = outlier_service
        self._smart_city_service = smart_city_service
        self._trend_service = trend_service
        self._llm_client = llm_client
        self._output_store = output_store
        self._audit = audit_logger

    def run_anomaly_report(
        self,
        *,
        agreement_id: str,
        asset_id: str,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
        robust_z_threshold: float,
    ) -> InsightExecutionResult:
        context = self._outlier_service.generate_outlier_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
            threshold=robust_z_threshold,
        )
        return self._run_llm_or_fallback(
            insight_type="anomaly-report",
            prompt_type="net_grid_outliers",
            agreement_id=agreement_id,
            asset_id=asset_id,
            context=context,
        )

    def run_city_status(
        self,
        *,
        agreement_id: str,
        asset_id: str,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
    ) -> InsightExecutionResult:
        context = self._smart_city_service.generate_correlation_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
        )
        return self._run_llm_or_fallback(
            insight_type="city-status",
            prompt_type="smart_city_correlation",
            agreement_id=agreement_id,
            asset_id=asset_id,
            context=context,
        )

    def run_energy_summary(
        self,
        *,
        agreement_id: str,
        asset_id: str,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
        forecast_alpha: float,
        trend_epsilon: float,
        daily_overview_strategy: Literal["strict_daily", "fallback_hourly"],
    ) -> InsightExecutionResult:
        context = self._trend_service.generate_trend_forecast_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
            forecast_alpha=forecast_alpha,
            trend_epsilon=trend_epsilon,
            daily_overview_strategy=daily_overview_strategy,
        )
        return self._run_llm_or_fallback(
            insight_type="energy-summary",
            prompt_type="energy_trend_forecast",
            agreement_id=agreement_id,
            asset_id=asset_id,
            context=context,
        )

    def _run_llm_or_fallback(
        self,
        *,
        insight_type: str,
        prompt_type: PromptInsightType,
        agreement_id: str,
        asset_id: str,
        context: dict[str, Any],
    ) -> InsightExecutionResult:
        rows_analyzed = self._rows_analyzed(context)
        if rows_analyzed <= 0:
            structured_output = self._rule_based_fallback(context=context)
            output_text = json.dumps(structured_output, ensure_ascii=True)
            openai_error = "LLM skipped due to insufficient data (rows_analyzed=0)"
            record = self._output_store.save(
                insight_type=insight_type,
                agreement_id=agreement_id,
                asset_id=asset_id,
                input_data=self._redact_pii(context),
                llm_model="rule-based-fallback",
                output_text=output_text,
                structured_output=structured_output,
            )
            self._audit.log(
                event="llm_skipped_insufficient_data",
                insight_type=insight_type,
                agreement_id=agreement_id,
                asset_id=asset_id,
                payload={"rows_analyzed": rows_analyzed},
            )
            return InsightExecutionResult(
                record=record,
                context=context,
                llm_used=False,
                openai_error=openai_error,
            )

        redacted_context = self._redact_pii(context)
        prompt = build_prompt_payload(insight_type=prompt_type, context=redacted_context)
        self._audit.log(
            event="prompt_prepared",
            insight_type=insight_type,
            agreement_id=agreement_id,
            asset_id=asset_id,
            payload={"prompt": prompt if prompt else {}},
        )

        llm_used = False
        llm_model = "rule-based-fallback"
        output_text = ""
        openai_error: str | None = None
        structured_output: dict[str, Any]
        try:
            output_text, raw_response = self._llm_client.create_chat_completion(
                messages=[
                    {"role": "system", "content": prompt["system"]},
                    {"role": "user", "content": prompt["user"]},
                ],
            )
            llm_used = True
            llm_model = str(raw_response.get("model") or "unknown-model")
            structured_output = self._parse_model_json(output_text)
            self._audit.log(
                event="llm_response",
                insight_type=insight_type,
                agreement_id=agreement_id,
                asset_id=asset_id,
                payload={"response": raw_response},
            )
        except (LLMRateLimitError, LLMUpstreamError, LLMClientError, ValueError) as error:
            structured_output = self._rule_based_fallback(context=context)
            output_text = json.dumps(structured_output, ensure_ascii=True)
            openai_error = str(error)
            self._audit.log(
                event="fallback_response",
                insight_type=insight_type,
                agreement_id=agreement_id,
                asset_id=asset_id,
                payload={"reason": "llm_unavailable_or_invalid_output"},
            )

        record = self._output_store.save(
            insight_type=insight_type,
            agreement_id=agreement_id,
            asset_id=asset_id,
            input_data=redacted_context,
            llm_model=llm_model,
            output_text=output_text,
            structured_output=structured_output,
        )
        return InsightExecutionResult(
            record=record,
            context=context,
            llm_used=llm_used,
            openai_error=openai_error,
        )

    @staticmethod
    def _rows_analyzed(context: dict[str, Any]) -> int:
        window = context.get("window", {})
        if not isinstance(window, dict):
            return 0
        rows = window.get("rows_analyzed", 0)
        try:
            return int(rows)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_model_json(model_text: str) -> dict[str, Any]:
        parsed = json.loads(model_text)
        if not isinstance(parsed, dict):
            raise ValueError("LLM output must be a JSON object")
        required = {"summary", "key_findings", "recommendations"}
        if required - set(parsed):
            raise ValueError("LLM output does not match expected schema")
        return parsed

    @staticmethod
    def _rule_based_fallback(*, context: dict[str, Any]) -> dict[str, Any]:
        summary = context.get("summary", {})
        narrative_hints = context.get("narrative_hints", [])
        key_findings = [str(item) for item in narrative_hints[:4]]
        if not key_findings:
            key_findings = ["No critical findings were detected for the requested interval."]
        recommendations = [
            "Validate highlighted periods against operational logs and maintenance records.",
            "Trigger a dashboard refresh once upstream LLM connectivity is restored.",
        ]
        return {
            "summary": (
                "Fallback insight generated from deterministic analytics context: "
                f"{summary}"
            ),
            "key_findings": key_findings,
            "recommendations": recommendations,
        }

    def _redact_pii(self, value: Any) -> Any:
        if isinstance(value, dict):
            redacted: dict[str, Any] = {}
            for key, item in value.items():
                key_lower = key.lower()
                if any(hint in key_lower for hint in _PII_KEY_HINTS):
                    redacted[key] = "***REDACTED***"
                    continue
                redacted[key] = self._redact_pii(item)
            return redacted
        if isinstance(value, list):
            return [self._redact_pii(item) for item in value]
        return value
