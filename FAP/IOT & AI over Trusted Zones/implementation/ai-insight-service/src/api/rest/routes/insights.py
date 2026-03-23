"""Insight routes for net-grid outlier analysis."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from requests import exceptions as requests_exceptions
from trino import exceptions as trino_exceptions

from src.config import load_config
from src.data.trino_client import TrinoQueryClient
from src.services.net_grid_insight_service import NetGridInsightService

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


def get_insight_service() -> NetGridInsightService:
    """Factory for the insights service."""
    settings = load_config()
    trino_client = TrinoQueryClient(settings.trino)
    return NetGridInsightService(trino_client=trino_client)


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
