"""Tests for orchestrator fallback behavior."""

from datetime import UTC, datetime

from src.llm.client import LLMUpstreamError
from src.observability.audit_log import AuditLogger
from src.services.insight_orchestrator import InsightOrchestrator
from src.storage.output_store import InMemoryOutputStore


class _FakeOutlierService:
    def generate_outlier_context(self, **kwargs):
        return {
            "window": {"rows_analyzed": 10},
            "summary": {"total_outliers": 1},
            "narrative_hints": ["Detected anomaly"],
        }


class _FakeSmartCityService:
    def generate_correlation_context(self, **kwargs):
        return {"summary": {"total_patterns": 1}, "narrative_hints": ["Detected pattern"]}


class _FakeTrendService:
    def generate_trend_forecast_context(self, **kwargs):
        return {"summary": {"forecast_points": 24}, "narrative_hints": ["Forecast generated"]}


class _FailingLLMClient:
    def create_chat_completion(self, **kwargs):
        raise LLMUpstreamError("upstream unavailable")


class _NoDataOutlierService:
    def generate_outlier_context(self, **kwargs):
        return {
            "window": {"rows_analyzed": 0},
            "summary": {"total_outliers": 0},
            "narrative_hints": ["No data in selected window."],
        }


def test_orchestrator_uses_rule_based_fallback_when_llm_fails() -> None:
    orchestrator = InsightOrchestrator(
        outlier_service=_FakeOutlierService(),
        smart_city_service=_FakeSmartCityService(),
        trend_service=_FakeTrendService(),
        llm_client=_FailingLLMClient(),
        output_store=InMemoryOutputStore(),
        audit_logger=AuditLogger(
            type(
                "Cfg",
                (),
                {
                    "enabled": False,
                    "log_prompts": False,
                    "log_responses": False,
                    "logger_name": "test",
                },
            )()
        ),
    )

    result = orchestrator.run_anomaly_report(
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 1, 1, tzinfo=UTC),
        end_ts=datetime(2026, 1, 2, tzinfo=UTC),
        timezone="UTC",
        robust_z_threshold=3.5,
    )
    assert result.llm_used is False
    assert result.record.llm_model == "rule-based-fallback"
    assert "recommendations" in result.record.structured_output
    assert result.openai_error == "upstream unavailable"


def test_orchestrator_skips_llm_when_rows_are_zero() -> None:
    orchestrator = InsightOrchestrator(
        outlier_service=_NoDataOutlierService(),
        smart_city_service=_FakeSmartCityService(),
        trend_service=_FakeTrendService(),
        llm_client=_FailingLLMClient(),
        output_store=InMemoryOutputStore(),
        audit_logger=AuditLogger(
            type(
                "Cfg",
                (),
                {
                    "enabled": False,
                    "log_prompts": False,
                    "log_responses": False,
                    "logger_name": "test",
                },
            )()
        ),
    )

    result = orchestrator.run_anomaly_report(
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 1, 1, tzinfo=UTC),
        end_ts=datetime(2026, 1, 2, tzinfo=UTC),
        timezone="UTC",
        robust_z_threshold=3.5,
    )
    assert result.llm_used is False
    assert result.record.llm_model == "rule-based-fallback"
    assert result.openai_error == "LLM skipped due to insufficient data (rows_analyzed=0)"
