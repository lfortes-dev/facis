"""In-memory AI output storage and latest cache access."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class AIOutputRecord:
    """Stored AI output entity for dashboard/API retrieval."""

    id: str
    insight_type: str
    agreement_id: str
    asset_id: str
    input_data: dict[str, Any]
    llm_model: str
    output_text: str
    structured_output: dict[str, Any]
    timestamp: datetime


class InMemoryOutputStore:
    """Process-local storage for AI outputs and latest per-insight entries."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[str, AIOutputRecord] = {}
        self._latest_by_type: dict[str, AIOutputRecord] = {}

    def save(
        self,
        *,
        insight_type: str,
        agreement_id: str,
        asset_id: str,
        input_data: dict[str, Any],
        llm_model: str,
        output_text: str,
        structured_output: dict[str, Any],
    ) -> AIOutputRecord:
        record = AIOutputRecord(
            id=str(uuid4()),
            insight_type=insight_type,
            agreement_id=agreement_id,
            asset_id=asset_id,
            input_data=deepcopy(input_data),
            llm_model=llm_model,
            output_text=output_text,
            structured_output=deepcopy(structured_output),
            timestamp=datetime.now(UTC),
        )
        with self._lock:
            self._by_id[record.id] = record
            self._latest_by_type[insight_type] = record
        return record

    def get(self, output_id: str) -> AIOutputRecord | None:
        with self._lock:
            record = self._by_id.get(output_id)
        return deepcopy(record) if record else None

    def latest_for_types(self, insight_types: tuple[str, ...]) -> dict[str, AIOutputRecord | None]:
        with self._lock:
            latest = {
                insight_type: self._latest_by_type.get(insight_type)
                for insight_type in insight_types
            }
        return {
            key: deepcopy(value) if value is not None else None
            for key, value in latest.items()
        }
