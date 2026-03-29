"""Structured audit logging for prompts and responses."""

from __future__ import annotations

import json
import logging
from typing import Any

from src.config import AuditConfig


class AuditLogger:
    """Writes structured prompt/response audit events to application logs."""

    def __init__(self, config: AuditConfig) -> None:
        self._config = config
        self._logger = logging.getLogger(config.logger_name)

    def log(
        self,
        *,
        event: str,
        insight_type: str,
        agreement_id: str,
        asset_id: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if not self._config.enabled:
            return
        event_data = {
            "event": event,
            "insight_type": insight_type,
            "agreement_id": agreement_id,
            "asset_id": asset_id,
            "payload": payload or {},
        }
        self._logger.info("audit_event=%s", json.dumps(event_data, sort_keys=True, default=str))
