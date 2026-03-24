"""Insight routes for net-grid and smart-city analysis."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from requests import exceptions as requests_exceptions
from trino import exceptions as trino_exceptions

from src.config import load_config
from src.data.trino_client import TrinoQueryClient
from src.services.net_grid_insight_service import NetGridInsightService
from src.services.smart_city_correlation_service import SmartCityCorrelationService
from src.services.trend_forecast_service import TrendForecastService

router = APIRouter(prefix="/api/v1/insights", tags=["insights"])
logger = logging.getLogger(__name__)


class NetGridOutlierRequest(BaseModel):
    """Request payload for net-grid outlier analysis."""

    start_ts: datetime = Field(
        description="Inclusive start timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-01T00:00:00Z"],
    )
    end_ts: datetime = Field(
        description="Exclusive end timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-08T00:00:00Z"],
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone label used for context generation and downstream narration.",
        examples=["UTC", "Europe/Berlin"],
    )
    robust_z_threshold: float = Field(
        default=3.5,
        gt=0,
        description=(
            "Sensitivity threshold for MAD-based robust z-score. "
            "Lower values detect more anomalies; higher values are stricter."
        ),
        examples=[3.5, 2.5, 4.5],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_ts": "2026-03-01T00:00:00Z",
                "end_ts": "2026-03-08T00:00:00Z",
                "timezone": "UTC",
                "robust_z_threshold": 3.5,
            }
        }
    }


class NetGridOutlierResponse(BaseModel):
    """Response payload containing structured context."""

    context: dict[str, Any] = Field(
        description=(
            "Structured context for LLM consumption including window summary, baseline "
            "statistics, detected outlier events, and narrative hints."
        )
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "context": {
                    "window": {
                        "start_ts": "2026-03-01T00:00:00+00:00",
                        "end_ts": "2026-03-08T00:00:00+00:00",
                        "timezone": "UTC",
                        "rows_analyzed": 168,
                    },
                    "baseline_stats": [],
                    "outlier_events": [],
                    "cost_anomalies": [],
                    "narrative_hints": [],
                    "summary": {
                        "total_outliers": 0,
                        "outliers_by_metric": {},
                        "selected_metrics": [],
                    },
                }
            }
        }
    }


class SmartCityCorrelationRequest(BaseModel):
    """Request payload for Smart City event/infrastructure correlation."""

    start_ts: datetime = Field(
        description="Inclusive start timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-01T00:00:00Z"],
    )
    end_ts: datetime = Field(
        description="Exclusive end timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-08T00:00:00Z"],
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone label used for context generation and downstream narration.",
        examples=["UTC", "Europe/Berlin"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_ts": "2026-03-01T00:00:00Z",
                "end_ts": "2026-03-08T00:00:00Z",
                "timezone": "UTC",
            }
        }
    }


class SmartCityCorrelationResponse(BaseModel):
    """Response payload containing Smart City correlation context."""

    context: dict[str, Any] = Field(
        description=(
            "Structured context for LLM consumption including event-response patterns, "
            "lag distribution, zone summaries, and confidence-ranked links."
        )
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "context": {
                    "window": {
                        "start_ts": "2026-03-01T00:00:00+00:00",
                        "end_ts": "2026-03-08T00:00:00+00:00",
                        "timezone": "UTC",
                        "rows_analyzed": 192,
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
            }
        }
    }


class EnergyTrendForecastRequest(BaseModel):
    """Request payload for energy trend and forecast analysis."""

    start_ts: datetime = Field(
        description="Inclusive start timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-01T00:00:00Z"],
    )
    end_ts: datetime = Field(
        description="Exclusive end timestamp for the analysis window (ISO 8601).",
        examples=["2026-03-08T00:00:00Z"],
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone label used for context generation and downstream narration.",
        examples=["UTC", "Europe/Berlin"],
    )
    forecast_alpha: float = Field(
        default=0.6,
        gt=0,
        le=1,
        description="Forecast blending factor in (0,1]; higher values amplify hourly seasonality.",
        examples=[0.4, 0.6, 0.8],
    )
    trend_epsilon: float = Field(
        default=0.02,
        ge=0,
        description="Normalized slope threshold for classifying trend as up/down/stable.",
        examples=[0.01, 0.02, 0.05],
    )
    daily_overview_strategy: Literal["strict_daily", "fallback_hourly"] = Field(
        default="strict_daily",
        description=(
            "How to compute daily_overview when daily Gold views are missing. "
            "`strict_daily` keeps zero-point daily summary; `fallback_hourly` estimates daily "
            "trend from hourly series."
        ),
        examples=["strict_daily", "fallback_hourly"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "start_ts": "2026-03-01T00:00:00Z",
                "end_ts": "2026-03-08T00:00:00Z",
                "timezone": "UTC",
                "forecast_alpha": 0.6,
                "trend_epsilon": 0.02,
                "daily_overview_strategy": "strict_daily",
            }
        }
    }


class EnergyTrendForecastResponse(BaseModel):
    """Response payload containing trend and forecast context."""

    context: dict[str, Any] = Field(
        description=(
            "Structured context for LLM consumption including trend signals, moving "
            "averages, seasonality profiles, and next-24h forecast points."
        )
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "context": {
                    "window": {
                        "start_ts": "2026-03-01T00:00:00+00:00",
                        "end_ts": "2026-03-08T00:00:00+00:00",
                        "timezone": "UTC",
                        "rows_analyzed": 168,
                    },
                    "trend_signals": {},
                    "moving_averages": {},
                    "seasonality_patterns": {},
                    "forecast_24h": [],
                    "daily_overview": {
                        "daily_cost_points": 0,
                        "daily_pv_points": 0,
                        "consumption_trend_daily": "stable",
                        "self_consumption_trend_daily": "stable",
                        "source": "daily_views",
                    },
                    "data_availability": {
                        "hourly_net_grid_weather": {"count": 0, "first": None, "last": None},
                        "daily_cost": {"count": 0, "first": None, "last": None},
                        "daily_pv_self_consumption": {"count": 0, "first": None, "last": None},
                    },
                    "narrative_hints": [],
                    "summary": {
                        "forecast_points": 0,
                        "tracked_metrics": [],
                        "daily_cost_points": 0,
                        "daily_pv_points": 0,
                    },
                }
            }
        }
    }


def get_insight_service() -> NetGridInsightService:
    """Factory for the insights service."""
    settings = load_config()
    trino_client = TrinoQueryClient(settings.trino)
    return NetGridInsightService(trino_client=trino_client)


def get_smart_city_correlation_service() -> SmartCityCorrelationService:
    """Factory for the Smart City correlation service."""
    settings = load_config()
    trino_client = TrinoQueryClient(settings.trino)
    return SmartCityCorrelationService(trino_client=trino_client)


def get_trend_forecast_service() -> TrendForecastService:
    """Factory for the trend and forecast service."""
    settings = load_config()
    trino_client = TrinoQueryClient(settings.trino)
    return TrendForecastService(trino_client=trino_client)


def _sanitize_upstream_error(error: Exception) -> str:
    """Map internal dependency failures to stable external API messages."""
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


@router.post(
    "/net-grid/outliers",
    response_model=NetGridOutlierResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze net-grid outliers",
    description=(
        "Query `gold.net_grid_hourly` for the requested period, compare consumption vs "
        "generation and cost patterns, detect robust statistical outliers (spikes/drops), "
        "and return structured context for LLM prompts."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid input parameters, such as start_ts >= end_ts."
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream query or processing failure (e.g., Trino connectivity)."
        },
    },
)
def net_grid_outliers(payload: NetGridOutlierRequest) -> NetGridOutlierResponse:
    """Analyze consumption/generation patterns and return LLM-ready context."""
    service = get_insight_service()
    try:
        context = service.generate_outlier_context(
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
            threshold=payload.robust_z_threshold,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - transport/runtime failures
        logger.exception(
            "net_grid_outliers_failed start_ts=%s end_ts=%s timezone=%s threshold=%s",
            payload.start_ts.isoformat(),
            payload.end_ts.isoformat(),
            payload.timezone,
            payload.robust_z_threshold,
        )
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error

    return NetGridOutlierResponse(context=context)


@router.post(
    "/smart-city/correlation",
    response_model=SmartCityCorrelationResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze Smart City event-response correlation",
    description=(
        "Query `gold.event_impact_daily` and `gold.streetlight_zone_hourly`, align by "
        "`zone_id` and calendar date (`event_date = CAST(hour AS DATE)`), and estimate "
        "event -> infrastructure response patterns.\n\n"
        "Statistical approach (hybrid):\n"
        "- Robust baseline shift with median and MAD\n"
        "- Lag-window evidence over 0-6h, 6-24h, and 24-48h\n"
        "- Composite confidence score for each event/zone pattern\n\n"
        "Formulas:\n"
        "- `MAD = median(|x_i - median(x)|)`\n"
        "- `robust_z = (x - median) / (1.4826 * MAD)`\n"
        "- `shift_pct = ((x_event - x_baseline) / |x_baseline|) * 100`\n"
        "- `response_score = 0.45 * anomaly_strength + 0.35 * lag_strength + 0.20 * severity_or_activity`\n\n"
        "Example:\n"
        "- Baseline zone power median = 50W, event-window average = 125W\n"
        "- `shift_pct = ((125 - 50)/50) * 100 = 150%`\n"
        "- If robust_z and early lag evidence are high, pattern confidence is ranked as high."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid input parameters, such as start_ts >= end_ts."
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream query or processing failure (e.g., Trino connectivity)."
        },
    },
)
def smart_city_correlation(
    payload: SmartCityCorrelationRequest,
) -> SmartCityCorrelationResponse:
    """Analyze event-to-streetlight response patterns for LLM-ready context."""
    service = get_smart_city_correlation_service()
    try:
        context = service.generate_correlation_context(
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - transport/runtime failures
        logger.exception(
            "smart_city_correlation_failed start_ts=%s end_ts=%s timezone=%s",
            payload.start_ts.isoformat(),
            payload.end_ts.isoformat(),
            payload.timezone,
        )
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error

    return SmartCityCorrelationResponse(context=context)


@router.post(
    "/energy/trend-forecast",
    response_model=EnergyTrendForecastResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze energy trends and next-24h forecast",
    description=(
        "Query `gold.net_grid_hourly`, `gold.weather_hourly`, `gold.energy_cost_daily`, "
        "and `gold.pv_self_consumption_daily` to build multi-day trend and seasonal context, "
        "then generate a deterministic next-24h hourly forecast for LLM summarization.\n\n"
        "Statistical approach:\n"
        "- Moving average: `MA_k(t) = (1/k) * sum(x_{t-i}, i=0..k-1)`\n"
        "- Trend slope: `slope = (x_t - x_{t-n}) / n` mapped to up/down/stable\n"
        "- Hourly seasonality index: `S_h = mean(x | hour=h)`\n"
        "- Forecast: `x_hat(t+1) = level_recent + alpha * (S_hour - seasonality_mean)`\n\n"
        "Example:\n"
        "- If recent net-grid level is 42.0 and hourly seasonal uplift is +3.0,\n"
        "  then `x_hat = 42.0 + 0.6 * 3.0 = 43.8`."
    ),
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "description": "Invalid input parameters, such as start_ts >= end_ts."
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "Upstream query or processing failure (e.g., Trino connectivity)."
        },
    },
)
def energy_trend_forecast(payload: EnergyTrendForecastRequest) -> EnergyTrendForecastResponse:
    """Analyze energy trends/seasonality and return 24h forecast context."""
    service = get_trend_forecast_service()
    try:
        context = service.generate_trend_forecast_context(
            start_ts=payload.start_ts,
            end_ts=payload.end_ts,
            timezone=payload.timezone,
            forecast_alpha=payload.forecast_alpha,
            trend_epsilon=payload.trend_epsilon,
            daily_overview_strategy=payload.daily_overview_strategy,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:  # pragma: no cover - transport/runtime failures
        logger.exception(
            "energy_trend_forecast_failed start_ts=%s end_ts=%s timezone=%s",
            payload.start_ts.isoformat(),
            payload.end_ts.isoformat(),
            payload.timezone,
        )
        raise HTTPException(status_code=502, detail=_sanitize_upstream_error(error)) from error

    return EnergyTrendForecastResponse(context=context)
