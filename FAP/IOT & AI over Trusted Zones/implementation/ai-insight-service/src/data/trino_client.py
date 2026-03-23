"""Trino data access helpers for net grid analysis."""

from __future__ import annotations

from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any

import requests
import trino
from trino.auth import Authentication, JWTAuthentication

from src.config import TrinoConfig

TARGET_SCHEMA = "gold"
TARGET_TABLE = "net_grid_hourly"
EVENT_IMPACT_DAILY_TABLE = "event_impact_daily"
STREETLIGHT_ZONE_HOURLY_TABLE = "streetlight_zone_hourly"


class TrinoQueryClient:
    """Small wrapper around Trino dbapi for read-only queries."""

    def __init__(self, config: TrinoConfig) -> None:
        self._config = config

    @staticmethod
    def _normalize_verify(value: bool | str) -> bool | str:
        """Normalize env-driven verify values into bool or CA path."""
        if isinstance(value, bool):
            return value
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
        return value

    def _fetch_oidc_password_token(self) -> str:
        token_url = self._config.oidc_token_url
        client_id = self._config.oidc_client_id
        client_secret = self._config.oidc_client_secret
        username = self._config.oidc_username
        password = self._config.oidc_password
        scope = self._config.oidc_scope

        if not token_url:
            raise ValueError("Trino OIDC password flow requires trino.oidc_token_url")
        if not client_id:
            raise ValueError("Trino OIDC password flow requires trino.oidc_client_id")
        if not client_secret:
            raise ValueError("Trino OIDC password flow requires trino.oidc_client_secret")
        if not username:
            raise ValueError("Trino OIDC password flow requires trino.oidc_username")
        if not password:
            raise ValueError("Trino OIDC password flow requires trino.oidc_password")

        form = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
        }
        if scope:
            form["scope"] = scope

        response = requests.post(
            token_url,
            data=form,
            timeout=20,
            verify=self._normalize_verify(self._config.oidc_verify),
        )
        response.raise_for_status()
        payload = response.json()
        access_token = payload.get("access_token")
        if not access_token:
            raise ValueError("OIDC token response does not include access_token")
        return str(access_token)

    def _build_auth(self) -> Authentication | None:
        if not self._config.oidc_token_url:
            return None

        token = self._fetch_oidc_password_token()
        return JWTAuthentication(token)

    def _connect(self) -> Any:
        auth = self._build_auth()
        return trino.dbapi.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.user,
            catalog=self._config.catalog,
            schema=self._config.schema,
            http_scheme=self._config.http_scheme,
            auth=auth,
            verify=self._normalize_verify(self._config.verify),
            request_timeout=float(self._config.request_timeout_seconds),
        )

    @staticmethod
    def _quote_ident(identifier: str) -> str:
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'

    def _target_schema(self) -> str:
        return TARGET_SCHEMA

    def _target_table(self) -> str:
        return TARGET_TABLE

    def _qualified_target_table(self) -> str:
        return (
            f"{self._quote_ident(self._target_schema())}."
            f"{self._quote_ident(self._target_table())}"
        )

    def _qualified_gold_table(self, table_name: str) -> str:
        return (
            f"{self._quote_ident(self._target_schema())}."
            f"{self._quote_ident(table_name)}"
        )

    @staticmethod
    def _to_utc_iso8601(value: datetime) -> str:
        """Normalize datetimes to UTC ISO-8601 (`...Z`) for Trino predicates."""
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=dt_timezone.utc)
        utc_value = normalized.astimezone(dt_timezone.utc)
        return utc_value.isoformat(timespec="seconds").replace("+00:00", "Z")

    def fetch_net_grid_hourly(
        self,
        start_ts: datetime,
        end_ts: datetime,
        timestamp_column: str,
        metric_columns: list[str],
    ) -> tuple[list[dict[str, Any]], str]:
        """Fetch rows for the selected time range and return rows + timestamp column."""
        timestamp_col = timestamp_column
        selected_columns = list(dict.fromkeys([timestamp_col, *metric_columns]))
        projected_sql = ", ".join(self._quote_ident(column) for column in selected_columns)

        start_iso = self._to_utc_iso8601(start_ts)
        end_iso = self._to_utc_iso8601(end_ts)

        query = (
            f"SELECT {projected_sql} FROM {self._qualified_target_table()} "
            f"WHERE {self._quote_ident(timestamp_col)} >= from_iso8601_timestamp('{start_iso}') "
            f"AND {self._quote_ident(timestamp_col)} < from_iso8601_timestamp('{end_iso}') "
            f"ORDER BY {self._quote_ident(timestamp_col)}"
        )

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            names = [desc[0] for desc in cursor.description]
            return [dict(zip(names, row)) for row in rows], timestamp_col
        finally:
            cursor.close()
            conn.close()

    def fetch_smart_city_correlation_rows(
        self,
        start_ts: datetime,
        end_ts: datetime,
    ) -> list[dict[str, Any]]:
        """Fetch Gold-only event/streetlight rows aligned by zone and calendar date."""
        start_iso = self._to_utc_iso8601(start_ts)
        end_iso = self._to_utc_iso8601(end_ts)
        event_table = self._qualified_gold_table(EVENT_IMPACT_DAILY_TABLE)
        streetlight_table = self._qualified_gold_table(STREETLIGHT_ZONE_HOURLY_TABLE)

        query = (
            "SELECT "
            "events.event_date, "
            "events.zone_id, "
            "events.event_type, "
            "events.event_count, "
            "events.avg_severity, "
            "events.active_count, "
            "streetlights.hour, "
            "streetlights.avg_dimming_pct, "
            "streetlights.total_power_w, "
            "streetlights.light_count "
            f"FROM {event_table} AS events "
            f"JOIN {streetlight_table} AS streetlights "
            "ON events.zone_id = streetlights.zone_id "
            "AND events.event_date = CAST(streetlights.hour AS DATE) "
            "WHERE events.event_date >= CAST(from_iso8601_timestamp("
            f"'{start_iso}') AS DATE) "
            "AND events.event_date < CAST(from_iso8601_timestamp("
            f"'{end_iso}') AS DATE) "
            "AND streetlights.hour >= from_iso8601_timestamp("
            f"'{start_iso}') "
            "AND streetlights.hour < from_iso8601_timestamp("
            f"'{end_iso}') "
            "ORDER BY events.event_date, events.zone_id, events.event_type, streetlights.hour"
        )

        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            names = [desc[0] for desc in cursor.description]
            return [dict(zip(names, row)) for row in rows]
        finally:
            cursor.close()
            conn.close()
