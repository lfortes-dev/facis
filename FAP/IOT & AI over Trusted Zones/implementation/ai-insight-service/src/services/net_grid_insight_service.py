"""Service layer to query net-grid data and build LLM-ready context."""

from __future__ import annotations

from datetime import datetime
import logging
from time import perf_counter
from typing import Any

from src.analytics.outliers import MetricSummary, detect_metric_outliers
from src.data.trino_client import TrinoQueryClient
from src.llm.context_builder import build_structured_context

TIMESTAMP_COLUMN = "hour"
METRIC_COLUMNS = (
    "avg_consumption_kw",
    "avg_generation_kw",
    "estimated_hourly_cost_eur",
)

logger = logging.getLogger(__name__)


class NetGridInsightService:
    """Orchestrates Trino query, anomaly detection, and context generation."""

    def __init__(self, trino_client: TrinoQueryClient) -> None:
        self._trino_client = trino_client

    def generate_outlier_context(
        self,
        *,
        start_ts: datetime,
        end_ts: datetime,
        timezone: str,
        threshold: float = 3.5,
    ) -> dict[str, Any]:
        """Generate outlier-focused context for downstream LLM use."""
        started_at = perf_counter()
        if start_ts >= end_ts:
            raise ValueError("start_ts must be earlier than end_ts")
        if threshold <= 0:
            raise ValueError("threshold must be greater than zero")

        metrics = list(METRIC_COLUMNS)
        records, timestamp_col = self._trino_client.fetch_net_grid_hourly(
            start_ts=start_ts,
            end_ts=end_ts,
            timestamp_column=TIMESTAMP_COLUMN,
            metric_columns=metrics,
        )

        all_events: list[dict[str, Any]] = []
        summaries: list[MetricSummary] = []
        for metric in metrics:
            events, summary = detect_metric_outliers(
                records=records,
                metric=metric,
                timestamp_column=timestamp_col,
                threshold=threshold,
            )
            all_events.extend(events)
            if summary is not None:
                summaries.append(summary)

        context = build_structured_context(
            start_ts=start_ts,
            end_ts=end_ts,
            timezone=timezone,
            total_rows=len(records),
            selected_metrics=metrics,
            summaries=summaries,
            outlier_events=all_events,
        )
        elapsed_ms = int((perf_counter() - started_at) * 1000)
        logger.info(
            "net_grid_outliers_completed start_ts=%s end_ts=%s timezone=%s "
            "rows=%d outliers=%d elapsed_ms=%d",
            start_ts.isoformat(),
            end_ts.isoformat(),
            timezone,
            len(records),
            len(all_events),
            elapsed_ms,
        )
        if len(records) == 0:
            logger.warning(
                "net_grid_outliers_no_data start_ts=%s end_ts=%s timezone=%s",
                start_ts.isoformat(),
                end_ts.isoformat(),
                timezone,
            )
        return context
