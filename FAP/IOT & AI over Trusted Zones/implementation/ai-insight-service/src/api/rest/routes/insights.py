"""Insight routes with policy, rate limits, and AI output storage."""

from __future__ import annotations

import logging
from datetime import datetime
from threading import Lock
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field
from requests import exceptions as requests_exceptions
from trino import exceptions as trino_exceptions

from src.config import load_config
from src.data.trino_client import TrinoQueryClient
from src.llm.client import OpenAICompatibleClient
from src.observability.audit_log import AuditLogger
from src.security.policy import AccessContext, PolicyDeniedError, PolicyEnforcer
from src.security.rate_limit import AgreementRateLimiter, RateLimitExceededError
from src.services.insight_orchestrator import InsightOrchestrator
from src.services.net_grid_insight_service import NetGridInsightService
from src.services.smart_city_correlation_service import SmartCityCorrelationService
from src.services.trend_forecast_service import TrendForecastService
from src.storage.insight_cache import create_insight_cache
from src.storage.output_store import AIOutputRecord, InMemoryOutputStore

insights_router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
outputs_router = APIRouter(prefix="/api/ai", tags=["insights"])
logger = logging.getLogger(__name__)

INSIGHT_TYPES: tuple[str, str, str] = ("energy-summary", "anomaly-report", "city-status")

_singletons_lock = Lock()
_singletons: dict[str, Any] = {}


class NetGridOutlierRequest(BaseModel):
    start_ts: datetime
    end_ts: datetime
    timezone: str = "UTC"
    robust_z_threshold: float = Field(default=3.5, gt=0)
    include_data: bool = False


class SmartCityCorrelationRequest(BaseModel):
    start_ts: datetime
    end_ts: datetime
    timezone: str = "UTC"
    include_data: bool = False


class EnergyTrendForecastRequest(BaseModel):
    start_ts: datetime
    end_ts: datetime
    timezone: str = "UTC"
    forecast_alpha: float = Field(default=0.6, gt=0, le=1)
    trend_epsilon: float = Field(default=0.02, ge=0)
    daily_overview_strategy: Literal["strict_daily", "fallback_hourly"] = "strict_daily"
    include_data: bool = False


class InsightMetadata(BaseModel):
    output_id: str
    llm_model: str
    timestamp: datetime
    llm_used: bool
    agreement_id: str
    asset_id: str
    llm_error: str | None = None


class InsightResponse(BaseModel):
    insight_type: str
    summary: str
    key_findings: list[str]
    recommendations: list[str]
    metadata: InsightMetadata
    data: dict[str, Any] | None = None


class LatestInsightEntry(BaseModel):
    cached_at: datetime
    output: InsightResponse


class LatestInsightsResponse(BaseModel):
    latest: dict[str, LatestInsightEntry | None]


class AIOutputEntityResponse(BaseModel):
    id: str
    insight_type: str
    agreement_id: str
    asset_id: str
    input_data: dict[str, Any]
    llm_model: str
    output_text: str
    structured_output: dict[str, Any]
    timestamp: datetime


def _sanitize_upstream_error(error: Exception) -> str:
    if isinstance(error, requests_exceptions.Timeout):
        return "Upstream Trino request timed out"
    if isinstance(error, requests_exceptions.SSLError):
        return "Upstream TLS verification failed"
    if isinstance(error, requests_exceptions.ConnectionError):
        return "Upstream Trino connection failed"
    if isinstance(error, trino_exceptions.TrinoConnectionError):
        return "Unable to connect to Trino"
    if isinstance(error, trino_exceptions.TrinoAuthError):
        return "Trino authentication failed"
    if isinstance(error, trino_exceptions.TrinoQueryError):
        return "Trino query failed"
    return "Upstream dependency failure while generating insight"


def _dependencies() -> dict[str, Any]:
    with _singletons_lock:
        if _singletons:
            return _singletons
        settings = load_config()
        trino_client = TrinoQueryClient(settings.trino)
        store = InMemoryOutputStore()
        insight_cache = create_insight_cache(settings.cache)
        _singletons.update(
            {
                "settings": settings,
                "policy": PolicyEnforcer(settings.policy),
                "limiter": AgreementRateLimiter(settings.rate_limit),
                "store": store,
                "insight_cache": insight_cache,
                "orchestrator": InsightOrchestrator(
                    outlier_service=NetGridInsightService(trino_client=trino_client),
                    smart_city_service=SmartCityCorrelationService(trino_client=trino_client),
                    trend_service=TrendForecastService(trino_client=trino_client),
                    llm_client=OpenAICompatibleClient(settings.llm),
                    output_store=store,
                    audit_logger=AuditLogger(settings.audit),
                    insight_cache=insight_cache,
                    cache_ttl_seconds=settings.cache.ttl_seconds,
                    cache_key_prefix=settings.cache.key_prefix,
                ),
            }
        )
        return _singletons


def _check_access(request: Request, response: Response) -> AccessContext:
    deps = _dependencies()
    policy: PolicyEnforcer = deps["policy"]
    limiter: AgreementRateLimiter = deps["limiter"]
    context = policy.build_context(request.headers)
    try:
        policy.enforce(context)
    except PolicyDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from error
    try:
        limiter.check(context.agreement_id)
    except RateLimitExceededError as error:
        raise HTTPException(
            status_code=429,
            detail="Agreement rate limit exceeded",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    return context


def _build_insight_response(
    *,
    insight_type: str,
    record: AIOutputRecord,
    llm_used: bool,
    llm_error: str | None = None,
    include_llm_error: bool = False,
    data: dict[str, Any] | None = None,
) -> InsightResponse:
    output = record.structured_output
    return InsightResponse(
        insight_type=insight_type,
        summary=str(output.get("summary", "")),
        key_findings=[str(item) for item in output.get("key_findings", [])],
        recommendations=[str(item) for item in output.get("recommendations", [])],
        metadata=InsightMetadata(
            output_id=record.id,
            llm_model=record.llm_model,
            timestamp=record.timestamp,
            llm_used=llm_used,
            agreement_id=record.agreement_id,
            asset_id=record.asset_id,
            llm_error=llm_error if include_llm_error else None,
        ),
        data=data,
    )


def _is_dev_mode(environment: str) -> bool:
    return environment.lower() in {"development", "dev", "local"}


@insights_router.post("/anomaly-report", response_model=InsightResponse)
def anomaly_report(
    payload: NetGridOutlierRequest,
    request: Request,
    response: Response,
) -> InsightResponse:
    access = _check_access(request, response)
    deps = _dependencies()
    orchestrator: InsightOrchestrator = deps["orchestrator"]
    settings = deps.get("settings")
    include_llm_error = bool(
        settings is not None and _is_dev_mode(settings.service.environment)
    )
    try:
        result = orchestrator.run_anomaly_report(
            agreement_id=access.agreement_id,
            asset_id=access.asset_id,
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
            robust_z_threshold=payload.robust_z_threshold,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except HTTPException:
        raise
    except Exception as error:
        logger.exception("anomaly_report_failed")
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error
    return _build_insight_response(
        insight_type="anomaly-report",
        record=result.record,
        llm_used=result.llm_used,
        llm_error=result.llm_error,
        include_llm_error=include_llm_error,
        data=result.context if payload.include_data else None,
    )


@insights_router.post("/city-status", response_model=InsightResponse)
def city_status(
    payload: SmartCityCorrelationRequest,
    request: Request,
    response: Response,
) -> InsightResponse:
    access = _check_access(request, response)
    deps = _dependencies()
    orchestrator: InsightOrchestrator = deps["orchestrator"]
    settings = deps.get("settings")
    include_llm_error = bool(
        settings is not None and _is_dev_mode(settings.service.environment)
    )
    try:
        result = orchestrator.run_city_status(
            agreement_id=access.agreement_id,
            asset_id=access.asset_id,
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("city_status_failed")
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error
    return _build_insight_response(
        insight_type="city-status",
        record=result.record,
        llm_used=result.llm_used,
        llm_error=result.llm_error,
        include_llm_error=include_llm_error,
        data=result.context if payload.include_data else None,
    )


@insights_router.post("/energy-summary", response_model=InsightResponse)
def energy_summary(
    payload: EnergyTrendForecastRequest,
    request: Request,
    response: Response,
) -> InsightResponse:
    access = _check_access(request, response)
    deps = _dependencies()
    orchestrator: InsightOrchestrator = deps["orchestrator"]
    settings = deps.get("settings")
    include_llm_error = bool(
        settings is not None and _is_dev_mode(settings.service.environment)
    )
    try:
        result = orchestrator.run_energy_summary(
            agreement_id=access.agreement_id,
            asset_id=access.asset_id,
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
            forecast_alpha=payload.forecast_alpha,
            trend_epsilon=payload.trend_epsilon,
            daily_overview_strategy=payload.daily_overview_strategy,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        logger.exception("energy_summary_failed")
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error
    return _build_insight_response(
        insight_type="energy-summary",
        record=result.record,
        llm_used=result.llm_used,
        llm_error=result.llm_error,
        include_llm_error=include_llm_error,
        data=result.context if payload.include_data else None,
    )


@insights_router.get("/latest", response_model=LatestInsightsResponse)
def latest_insights() -> LatestInsightsResponse:
    deps = _dependencies()
    store: InMemoryOutputStore = deps["store"]
    latest = store.latest_for_types(INSIGHT_TYPES)
    mapped: dict[str, LatestInsightEntry | None] = {}
    for insight_type in INSIGHT_TYPES:
        record = latest.get(insight_type)
        if record is None:
            mapped[insight_type] = None
            continue
        mapped[insight_type] = LatestInsightEntry(
            cached_at=record.timestamp,
            output=_build_insight_response(
                insight_type=insight_type,
                record=record,
                llm_used=record.llm_model != "rule-based-fallback",
            ),
        )
    return LatestInsightsResponse(latest=mapped)


@outputs_router.get("/outputs/{output_id}", response_model=AIOutputEntityResponse)
def get_output(output_id: str) -> AIOutputEntityResponse:
    deps = _dependencies()
    store: InMemoryOutputStore = deps["store"]
    record = store.get(output_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Output not found")
    return AIOutputEntityResponse(
        id=record.id,
        insight_type=record.insight_type,
        agreement_id=record.agreement_id,
        asset_id=record.asset_id,
        input_data=record.input_data,
        llm_model=record.llm_model,
        output_text=record.output_text,
        structured_output=record.structured_output,
        timestamp=record.timestamp,
    )
