"""Unit tests for Trino authentication and query generation."""

from datetime import datetime, timedelta, timezone

from trino.auth import JWTAuthentication

from src.config import TrinoConfig
from src.data.trino_client import TrinoQueryClient


class _FakeCursor:
    def __init__(
        self,
        *,
        description: list[tuple[str, None, None, None, None, None, None]],
        rows: list[tuple[object, ...]],
        scripted_responses: list[
            tuple[list[tuple[str, None, None, None, None, None, None]], list[tuple[object, ...]]]
        ] | None = None,
    ) -> None:
        self.executed_queries: list[str] = []
        self.description = description
        self._rows = rows
        self._scripted_responses = scripted_responses or []
        self._response_index = 0

    def execute(self, query: str) -> None:
        self.executed_queries.append(query)
        if self._scripted_responses and self._response_index < len(self._scripted_responses):
            description, rows = self._scripted_responses[self._response_index]
            self.description = description
            self._rows = rows
            self._response_index += 1

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows

    def close(self) -> None:
        return None


class _FakeConnection:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        return None


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


def test_build_auth_without_oidc_raises() -> None:
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="test"))
    try:
        client._build_auth()
        assert False, "Expected ValueError when OIDC password-flow config is missing"
    except ValueError as error:
        assert "trino.oidc_token_url" in str(error)


def test_target_schema_defaults_to_gold() -> None:
    client = TrinoQueryClient(
        TrinoConfig(host="localhost", port=8080, user="test", schema="default")
    )
    assert client._qualified_target_table() == '"gold"."net_grid_hourly"'


def test_target_schema_can_be_overridden() -> None:
    client = TrinoQueryClient(
        TrinoConfig(
            host="localhost",
            port=8080,
            user="test",
            schema="default",
            target_schema="silver",
        )
    )
    assert client._qualified_target_table() == '"silver"."net_grid_hourly"'


def test_to_utc_iso8601_normalizes_timezone_offset() -> None:
    value = datetime(2026, 3, 1, 2, 30, tzinfo=timezone(timedelta(hours=2)))
    assert TrinoQueryClient._to_utc_iso8601(value) == "2026-03-01T00:30:00Z"


def test_net_grid_table_name_can_be_overridden(monkeypatch) -> None:
    cursor = _FakeCursor(
        description=[
            ("hour", None, None, None, None, None, None),
            ("avg_consumption_kw", None, None, None, None, None, None),
        ],
        rows=[("2026-03-01T00:00:00+00:00", 12.0)],
    )
    connection = _FakeConnection(cursor)
    client = TrinoQueryClient(
        TrinoConfig(
            host="localhost",
            port=8080,
            user="test",
            table_net_grid_hourly="custom_net_grid",
        )
    )
    monkeypatch.setattr(client, "_connect", lambda: connection)

    client.fetch_net_grid_hourly(
        start_ts=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
        end_ts=datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc),
        timestamp_column="hour",
        metric_columns=["avg_consumption_kw"],
    )
    assert 'FROM "gold"."custom_net_grid"' in cursor.executed_queries[0]


def test_fetch_net_grid_hourly_builds_projected_query_with_utc_bounds(monkeypatch) -> None:
    cursor = _FakeCursor(
        description=[
            ("hour", None, None, None, None, None, None),
            ("avg_consumption_kw", None, None, None, None, None, None),
            ("avg_generation_kw", None, None, None, None, None, None),
            ("estimated_hourly_cost_eur", None, None, None, None, None, None),
        ],
        rows=[("2026-03-01T00:00:00+00:00", 12.0, 4.0, 1.5)],
    )
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


def test_fetch_smart_city_correlation_rows_uses_gold_only_join(monkeypatch) -> None:
    cursor = _FakeCursor(
        description=[
            ("event_date", None, None, None, None, None, None),
            ("zone_id", None, None, None, None, None, None),
            ("event_type", None, None, None, None, None, None),
            ("event_count", None, None, None, None, None, None),
            ("avg_severity", None, None, None, None, None, None),
            ("active_count", None, None, None, None, None, None),
            ("hour", None, None, None, None, None, None),
            ("avg_dimming_pct", None, None, None, None, None, None),
            ("total_power_w", None, None, None, None, None, None),
            ("light_count", None, None, None, None, None, None),
        ],
        rows=[
            (
                "2026-03-01",
                "zone-a",
                "accident",
                2,
                2.5,
                1,
                "2026-03-01T03:00:00+00:00",
                72.0,
                1320.0,
                24,
            )
        ],
    )
    connection = _FakeConnection(cursor)
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="test"))
    monkeypatch.setattr(client, "_connect", lambda: connection)

    rows = client.fetch_smart_city_correlation_rows(
        start_ts=datetime(2026, 3, 1, 2, 0, tzinfo=timezone(timedelta(hours=2))),
        end_ts=datetime(2026, 3, 2, 2, 0, tzinfo=timezone(timedelta(hours=2))),
    )

    assert len(rows) == 1
    executed = cursor.executed_queries[0]
    assert 'FROM "gold"."event_impact_daily" AS events' in executed
    assert 'JOIN "gold"."streetlight_zone_hourly" AS streetlights' in executed
    assert "events.zone_id = streetlights.zone_id" in executed
    assert "events.event_date = CAST(streetlights.hour AS DATE)" in executed
    assert "events.event_date >= CAST(from_iso8601_timestamp('2026-03-01T00:00:00Z') AS DATE)" in executed
    assert "events.event_date < CAST(from_iso8601_timestamp('2026-03-02T00:00:00Z') AS DATE)" in executed
    assert "streetlights.hour >= from_iso8601_timestamp('2026-03-01T00:00:00Z')" in executed
    assert "streetlights.hour < from_iso8601_timestamp('2026-03-02T00:00:00Z')" in executed


def test_fetch_energy_trend_forecast_rows_queries_expected_gold_views(monkeypatch) -> None:
    cursor = _FakeCursor(
        description=[("placeholder", None, None, None, None, None, None)],
        rows=[],
        scripted_responses=[
            (
                [
                    ("hour", None, None, None, None, None, None),
                    ("avg_consumption_kw", None, None, None, None, None, None),
                    ("avg_generation_kw", None, None, None, None, None, None),
                    ("net_grid_kw", None, None, None, None, None, None),
                    ("avg_price_eur_per_kwh", None, None, None, None, None, None),
                    ("estimated_hourly_cost_eur", None, None, None, None, None, None),
                    ("avg_temperature_c", None, None, None, None, None, None),
                    ("avg_irradiance_w_m2", None, None, None, None, None, None),
                    ("avg_humidity_pct", None, None, None, None, None, None),
                    ("avg_wind_speed_ms", None, None, None, None, None, None),
                    ("avg_cloud_cover_pct", None, None, None, None, None, None),
                ],
                [("2026-03-01T00:00:00+00:00", 52.0, 10.0, 42.0, 0.2, 8.4, 18.0, 120.0, 65.0, 3.0, 42.0)],
            ),
            (
                [
                    ("cost_date", None, None, None, None, None, None),
                    ("total_consumption_kw", None, None, None, None, None, None),
                    ("avg_cost_per_reading_eur", None, None, None, None, None, None),
                    ("peak_consumption_kw", None, None, None, None, None, None),
                    ("offpeak_consumption_kw", None, None, None, None, None, None),
                    ("avg_peak_price_eur", None, None, None, None, None, None),
                    ("avg_offpeak_price_eur", None, None, None, None, None, None),
                    ("reading_count", None, None, None, None, None, None),
                ],
                [("2026-03-01", 320.0, 4.0, 130.0, 190.0, 0.22, 0.18, 24)],
            ),
            (
                [
                    ("sc_date", None, None, None, None, None, None),
                    ("total_consumption_kw", None, None, None, None, None, None),
                    ("total_generation_kw", None, None, None, None, None, None),
                    ("self_consumed_kw", None, None, None, None, None, None),
                    ("exported_kw", None, None, None, None, None, None),
                    ("imported_kw", None, None, None, None, None, None),
                    ("self_consumption_ratio", None, None, None, None, None, None),
                    ("autarky_ratio", None, None, None, None, None, None),
                ],
                [("2026-03-01", 320.0, 210.0, 170.0, 40.0, 150.0, 0.81, 0.53)],
            ),
        ],
    )
    connection = _FakeConnection(cursor)
    client = TrinoQueryClient(TrinoConfig(host="localhost", port=8080, user="test"))
    monkeypatch.setattr(client, "_connect", lambda: connection)

    dataset = client.fetch_energy_trend_forecast_rows(
        start_ts=datetime(2026, 3, 1, 2, 0, tzinfo=timezone(timedelta(hours=2))),
        end_ts=datetime(2026, 3, 2, 2, 0, tzinfo=timezone(timedelta(hours=2))),
    )

    assert len(dataset["hourly"]) == 1
    assert len(dataset["daily_cost"]) == 1
    assert len(dataset["daily_pv"]) == 1

    hourly_query = cursor.executed_queries[0]
    assert 'FROM "gold"."net_grid_hourly" AS grid' in hourly_query
    assert 'LEFT JOIN "gold"."weather_hourly" AS weather' in hourly_query
    assert "grid.hour = weather.hour" in hourly_query

    daily_cost_query = cursor.executed_queries[1]
    assert 'FROM "gold"."energy_cost_daily"' in daily_cost_query
    assert "cost_date >= CAST(from_iso8601_timestamp('2026-03-01T00:00:00Z') AS DATE)" in daily_cost_query
    assert "cost_date < CAST(from_iso8601_timestamp('2026-03-02T00:00:00Z') AS DATE)" in daily_cost_query

    daily_pv_query = cursor.executed_queries[2]
    assert 'FROM "gold"."pv_self_consumption_daily"' in daily_pv_query
    assert "sc_date >= CAST(from_iso8601_timestamp('2026-03-01T00:00:00Z') AS DATE)" in daily_pv_query
    assert "sc_date < CAST(from_iso8601_timestamp('2026-03-02T00:00:00Z') AS DATE)" in daily_pv_query
