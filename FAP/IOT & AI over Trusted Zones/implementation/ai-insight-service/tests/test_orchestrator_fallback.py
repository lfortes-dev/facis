"""Tests for orchestrator fallback behavior."""

from datetime import UTC, datetime

from src.llm.client import LLMUpstreamError
from src.observability.audit_log import AuditLogger
from src.services.insight_orchestrator import InsightOrchestrator
from src.storage.insight_cache import NoopInsightCache
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
        insight_cache=NoopInsightCache(),
        cache_ttl_seconds=300,
        cache_key_prefix="test:cache",
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
    assert result.llm_error == "upstream unavailable"


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
        insight_cache=NoopInsightCache(),
        cache_ttl_seconds=300,
        cache_key_prefix="test:cache",
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
    assert result.llm_error == "LLM skipped due to insufficient data (rows_analyzed=0)"


class _CountingOutlierService:
    def __init__(self) -> None:
        self.calls = 0

    def generate_outlier_context(self, **kwargs):
        self.calls += 1
        return {
            "window": {"rows_analyzed": 10},
            "summary": {"total_outliers": 1},
            "narrative_hints": ["Detected anomaly"],
        }


class _SuccessfulLLMClient:
    def __init__(self) -> None:
        self.calls = 0

    def create_chat_completion(self, **kwargs):
        self.calls += 1
        return (
            '{"summary":"cached","key_findings":["f1"],"recommendations":["r1"]}',
            {"model": "gpt-test"},
        )


class _MemoryInsightCache:
    def __init__(self) -> None:
        self.data: dict[str, dict] = {}
        self.last_ttl: int | None = None

    def get(self, key: str) -> dict | None:
        return self.data.get(key)

    def set(self, key: str, value: dict, ttl_seconds: int) -> None:
        self.last_ttl = ttl_seconds
        self.data[key] = value


def test_orchestrator_uses_cache_hit_to_skip_llm_and_context_fetch() -> None:
    outlier_service = _CountingOutlierService()
    llm_client = _SuccessfulLLMClient()
    cache = _MemoryInsightCache()
    orchestrator = InsightOrchestrator(
        outlier_service=outlier_service,
        smart_city_service=_FakeSmartCityService(),
        trend_service=_FakeTrendService(),
        llm_client=llm_client,
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
        insight_cache=cache,  # type: ignore[arg-type]
        cache_ttl_seconds=300,
        cache_key_prefix="test:cache",
    )

    first = orchestrator.run_anomaly_report(
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 1, 1, tzinfo=UTC),
        end_ts=datetime(2026, 1, 2, tzinfo=UTC),
        timezone="UTC",
        robust_z_threshold=3.5,
    )
    second = orchestrator.run_anomaly_report(
        agreement_id="agreement-1",
        asset_id="asset-7",
        start_ts=datetime(2026, 1, 1, tzinfo=UTC),
        end_ts=datetime(2026, 1, 2, tzinfo=UTC),
        timezone="UTC",
        robust_z_threshold=3.5,
    )

    assert first.llm_used is True
    assert second.llm_used is False
    assert llm_client.calls == 1
    assert outlier_service.calls == 1
    assert second.record.structured_output["summary"] == "cached"
    assert cache.last_ttl == 300
