"""Integration fixtures for full API pipeline tests with mocked dependencies."""

from __future__ import annotations

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from src.api.rest.app import create_app
from src.api.rest.routes import insights
from src.data.trino_client import TrinoQueryClient
from src.llm.client import OpenAICompatibleClient


def _install_mock_data_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        TrinoQueryClient,
        "fetch_net_grid_hourly",
        lambda self, **kwargs: (
            [
                {
                    "hour": "2026-03-01T00:00:00+00:00",
                    "avg_consumption_kw": 52.0,
                    "avg_generation_kw": 10.0,
                    "estimated_hourly_cost_eur": 8.4,
                },
                {
                    "hour": "2026-03-01T01:00:00+00:00",
                    "avg_consumption_kw": 53.0,
                    "avg_generation_kw": 10.0,
                    "estimated_hourly_cost_eur": 8.6,
                },
                {
                    "hour": "2026-03-01T02:00:00+00:00",
                    "avg_consumption_kw": 120.0,
                    "avg_generation_kw": 9.0,
                    "estimated_hourly_cost_eur": 25.0,
                },
            ],
            "hour",
        ),
    )
    monkeypatch.setattr(
        TrinoQueryClient,
        "fetch_smart_city_correlation_rows",
        lambda self, **kwargs: [
            {
                "event_date": "2026-03-01",
                "zone_id": "zone-a",
                "event_type": "accident",
                "event_count": 2,
                "avg_severity": 2.5,
                "active_count": 1,
                "hour": "2026-03-01T01:00:00+00:00",
                "avg_dimming_pct": 82.0,
                "total_power_w": 250.0,
                "light_count": 20,
            }
        ],
    )
    monkeypatch.setattr(
        TrinoQueryClient,
        "fetch_energy_trend_forecast_rows",
        lambda self, **kwargs: {
            "hourly": [
                {
                    "hour": "2026-03-01T00:00:00+00:00",
                    "avg_consumption_kw": 52.0,
                    "avg_generation_kw": 10.0,
                    "net_grid_kw": 42.0,
                    "avg_price_eur_per_kwh": 0.2,
                    "estimated_hourly_cost_eur": 8.4,
                    "avg_temperature_c": 18.0,
                    "avg_irradiance_w_m2": 120.0,
                    "avg_humidity_pct": 65.0,
                    "avg_wind_speed_ms": 3.0,
                    "avg_cloud_cover_pct": 40.0,
                },
                {
                    "hour": "2026-03-01T01:00:00+00:00",
                    "avg_consumption_kw": 54.0,
                    "avg_generation_kw": 11.0,
                    "net_grid_kw": 43.0,
                    "avg_price_eur_per_kwh": 0.21,
                    "estimated_hourly_cost_eur": 9.03,
                    "avg_temperature_c": 17.8,
                    "avg_irradiance_w_m2": 90.0,
                    "avg_humidity_pct": 66.0,
                    "avg_wind_speed_ms": 2.8,
                    "avg_cloud_cover_pct": 42.0,
                },
            ],
            "daily_cost": [
                {
                    "cost_date": "2026-03-01",
                    "total_consumption_kw": 320.0,
                    "avg_cost_per_reading_eur": 4.0,
                    "peak_consumption_kw": 130.0,
                    "offpeak_consumption_kw": 190.0,
                    "avg_peak_price_eur": 0.22,
                    "avg_offpeak_price_eur": 0.18,
                    "reading_count": 24,
                }
            ],
            "daily_pv": [
                {
                    "sc_date": "2026-03-01",
                    "total_consumption_kw": 320.0,
                    "total_generation_kw": 210.0,
                    "self_consumed_kw": 170.0,
                    "exported_kw": 40.0,
                    "imported_kw": 150.0,
                    "self_consumption_ratio": 0.81,
                    "autarky_ratio": 0.53,
                }
            ],
        },
    )


def _install_mock_llm_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        OpenAICompatibleClient,
        "create_chat_completion",
        lambda self, **kwargs: (
            '{"summary":"integration-ok","key_findings":["k1"],"recommendations":["r1"]}',
            {"model": "gpt-test"},
        ),
    )


def _base_env() -> dict[str, str]:
    return {
        "FACIS_ENV": "development",
        "AI_INSIGHT_CACHE__ENABLED": "false",
        "AI_INSIGHT_AUDIT__ENABLED": "false",
        "AI_INSIGHT_TRINO__HOST": "mocked-trino",
        "AI_INSIGHT_TRINO__PORT": "8080",
        "AI_INSIGHT_TRINO__USER": "trino",
        "AI_INSIGHT_TRINO__CATALOG": "hive",
        "AI_INSIGHT_TRINO__SCHEMA": "default",
        "AI_INSIGHT_TRINO__TARGET_SCHEMA": "gold",
        "AI_INSIGHT_TRINO__HTTP_SCHEME": "http",
        "AI_INSIGHT_TRINO__VERIFY": "false",
        "AI_INSIGHT_TRINO__REQUEST_TIMEOUT_SECONDS": "20",
        "AI_INSIGHT_LLM__API_KEY": "test-key",
        "AI_INSIGHT_LLM__CHAT_COMPLETIONS_URL": "https://example.ai/openai/deployments/gpt-test/chat/completions?api-version=2025-01-01-preview",
        "AI_INSIGHT_LLM__MODEL": "gpt-test",
    }


@pytest.fixture()
def integration_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Main integration client with policy/rate limits disabled."""
    env_map = {
        **_base_env(),
        "AI_INSIGHT_POLICY__ENABLED": "false",
        "AI_INSIGHT_RATE_LIMIT__ENABLED": "false",
    }
    for key, value in env_map.items():
        monkeypatch.setenv(key, value)
    _install_mock_data_sources(monkeypatch)
    _install_mock_llm_success(monkeypatch)

    insights._singletons.clear()
    client = TestClient(create_app())
    try:
        yield client
    finally:
        insights._singletons.clear()


@pytest.fixture()
def governed_integration_client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Integration client with real policy/rate-limit checks enabled."""
    env_map = {
        **_base_env(),
        "AI_INSIGHT_POLICY__ENABLED": "true",
        "AI_INSIGHT_RATE_LIMIT__ENABLED": "true",
        "AI_INSIGHT_RATE_LIMIT__REQUESTS_PER_MINUTE": "1",
    }
    for key, value in env_map.items():
        monkeypatch.setenv(key, value)
    _install_mock_data_sources(monkeypatch)
    _install_mock_llm_success(monkeypatch)

    insights._singletons.clear()
    client = TestClient(create_app())
    try:
        yield client
    finally:
        insights._singletons.clear()


@pytest.fixture()
def access_headers() -> dict[str, str]:
    return {
        "x-agreement-id": "agreement-1",
        "x-asset-id": "asset-7",
        "x-user-roles": "ai_insight_consumer",
    }
