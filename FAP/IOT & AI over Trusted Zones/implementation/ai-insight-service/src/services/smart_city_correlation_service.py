"""Service layer for Smart City event/infrastructure correlation context."""

from __future__ import annotations

from datetime import datetime
import logging
from time import perf_counter
from typing import Any

from src.analytics.smart_city_correlation import analyze_event_infrastructure_correlation
from src.data.trino_client import TrinoQueryClient
from src.llm.context_builder import build_smart_city_correlation_context

logger = logging.getLogger(__name__)


class SmartCityCorrelationService:
    """Orchestrates Gold query, hybrid correlation, and context generation."""

    def __init__(self, trino_client: TrinoQueryClient) -> None:
        self._trino_client = trino_client

    def generate_correlation_context(
        self,
        *,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
    ) -> dict[str, Any]:
        """Generate Smart City correlation context for downstream LLM use."""
        started_at = perf_counter()
        if start_ts >= end_ts:
            raise ValueError("start_ts must be earlier than end_ts")

        rows = self._trino_client.fetch_smart_city_correlation_rows(
            start_ts=start_ts,
            end_ts=end_ts,
        )
        correlation_result = analyze_event_infrastructure_correlation(rows)
        context = build_smart_city_correlation_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
            total_rows=len(rows),
            correlation_result=correlation_result,
        )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "smart_city_correlation_completed start_ts=%s end_ts=%s timezone=%s "
            "rows=%d patterns=%d high_confidence_links=%d elapsed_ms=%d",
            start_ts.isoformat(),
            end_ts.isoformat(),
            timezone,
            len(rows),
            len(correlation_result.event_response_patterns),
            len(correlation_result.high_confidence_links),
            elapsed_ms,
        )
        if len(rows) == 0:
            logger.warning(
                "smart_city_correlation_no_data start_ts=%s end_ts=%s timezone=%s",
                start_ts.isoformat(),
                end_ts.isoformat(),
                timezone,
            )
        return context
