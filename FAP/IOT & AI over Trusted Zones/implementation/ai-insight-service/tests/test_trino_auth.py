"""Unit tests for Trino authentication and query generation."""

from datetime import datetime, timedelta, timezone

from trino.auth import JWTAuthentication

from src.config import TrinoConfig
from src.data.trino_client import TrinoQueryClient


class _FakeCursor:
    def __init__(self) -> None:
        self.executed_queries: list[str] = []
        self.description = [
            ("hour", None, None, None, None, None, None),
            ("avg_consumption_kw", None, None, None, None, None, None),
            ("avg_generation_kw", None, None, None, None, None, None),
            ("estimated_hourly_cost_eur", None, None, None, None, None, None),
        ]

    def execute(self, query: str) -> None:
        self.executed_queries.append(query)

    def fetchall(self) -> list[tuple[object, ...]]:
        return [("2026-03-01T00:00:00+00:00", 12.0, 4.0, 1.5)]

    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        return None


def test_build_auth_none_returns_none() -> None:
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="trino"))
    assert client._build_auth() is None


def test_build_auth_keycloak_password_returns_jwt(monkeypatch) -> None:
    client = TrinoQueryClient(
        TrinoConfig(
            host="localhost",
            port=8080,
            user="test",
            oidc_token_url="https://identity.local/token",
            oidc_client_id="oidc",
            oidc_client_secret="secret",
            oidc_username="test",
            oidc_password="password",
        )
    )
    monkeypatch.setattr(client, "_fetch_oidc_password_token", lambda: "token-value")
    assert isinstance(client._build_auth(), JWTAuthentication)


def test_build_auth_without_oidc_returns_none() -> None:
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="test"))
    assert client._build_auth() is None


def test_target_schema_is_fixed_to_gold() -> None:
    client = TrinoQueryClient(
        TrinoConfig(host="localhost", port=8080, user="test", schema="default")
    )
    assert client._qualified_target_table() == '"gold"."net_grid_hourly"'


def test_to_utc_iso8601_normalizes_timezone_offset() -> None:
    value = datetime(2026, 3, 1, 2, 30, tzinfo=timezone(timedelta(hours=2)))
    assert TrinoQueryClient._to_utc_iso8601(value) == "2026-03-01T00:30:00Z"


def test_fetch_net_grid_hourly_builds_projected_query_with_utc_bounds(monkeypatch) -> None:
    cursor = _FakeCursor()
    connection = _FakeConnection(cursor)
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="test"))
    monkeypatch.setattr(client, "_connect", lambda: connection)

    start_ts = datetime(2026, 3, 1, 2, 0, tzinfo=timezone(timedelta(hours=2)))
    end_ts = datetime(2026, 3, 1, 3, 0, tzinfo=timezone(timedelta(hours=2)))

    rows, timestamp_col = client.fetch_net_grid_hourly(
        start_ts=start_ts,
        end_ts=end_ts,
        timestamp_column="hour",
        metric_columns=["avg_consumption_kw", "avg_generation_kw", "estimated_hourly_cost_eur"],
    )

    assert timestamp_col == "hour"
    assert len(rows) == 1
    executed = cursor.executed_queries[0]
    assert 'SELECT "hour", "avg_consumption_kw", "avg_generation_kw", "estimated_hourly_cost_eur"' in executed
    assert "FROM \"gold\".\"net_grid_hourly\"" in executed
    assert "from_iso8601_timestamp('2026-03-01T00:00:00Z')" in executed
    assert "from_iso8601_timestamp('2026-03-01T01:00:00Z')" in executed
