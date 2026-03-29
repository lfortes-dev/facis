# FACIS AI Insight Service

FastAPI service that generates governed AI insights from energy and IoT datasets.
The API combines Trino-backed analytics, policy enforcement, rate limiting, caching,
and OpenAI-compatible LLM summarization.

## What This Service Provides

- Governed insight endpoints for anomaly, city status, and energy summary workflows.
- Policy checks (`agreement`, `asset`, `role`) and agreement-scoped rate limiting.
- Trino data access with OIDC password-flow JWT authentication.
- Redis-backed cache for repeated insight requests.
- OpenAPI-first API documentation served by the runtime.

## Quick Start (Local)

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
pip install -e .
python -m src.main
```

Health:

```bash
curl http://localhost:8080/api/v1/health
```

Swagger/ReDoc:

- `http://localhost:8080/docs`
- `http://localhost:8080/redoc`

## Quick Start (Docker Compose)

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
docker compose up --build
```

Stop:

```bash
docker compose down
```

## API Usage Examples

```bash
# Energy summary
curl -X POST http://localhost:8080/api/v1/insights/energy-summary \
  -H "x-agreement-id: agreement-1" \
  -H "x-asset-id: asset-7" \
  -H "x-user-roles: ai_insight_consumer" \
  -d '{"start_ts":"2026-03-01T00:00:00Z","end_ts":"2026-03-02T00:00:00Z"}'

# Anomaly report
curl -X POST http://localhost:8080/api/v1/insights/anomaly-report \
  -H "x-agreement-id: agreement-1" \
  -H "x-asset-id: asset-7" \
  -H "x-user-roles: ai_insight_consumer" \
  -d '{"start_ts":"2026-03-01T00:00:00Z","end_ts":"2026-03-02T00:00:00Z"}'

# City status
curl -X POST http://localhost:8080/api/v1/insights/city-status \
  -H "x-agreement-id: agreement-1" \
  -H "x-asset-id: asset-7" \
  -H "x-user-roles: ai_insight_consumer" \
  -d '{"start_ts":"2026-03-01T00:00:00Z","end_ts":"2026-03-02T00:00:00Z"}'
```

## Testing and Linting

```bash
pip install -e ".[dev]"
python -m pytest -v
python -m ruff check src tests
```

### Integration Tests (Mocked Trino)

Integration tests run the full API pipeline while mocking Trino data access and
using a deterministic LLM stub. They do not require an external Trino server.

Run only integration tests:

```bash
python -m pytest -v tests/integration
```

Run mocked unit pipeline tests (baseline):

```bash
python -m pytest -v tests/test_service.py tests/test_smart_city_correlation_service.py tests/test_trend_forecast_service.py
```

## Configuration Model

Configuration is layered (later sources override earlier sources):

1. `config/default.yaml`
2. `config/{FACIS_ENV}.yaml` (for example `development`, `test`, `production`)
3. Environment variables prefixed with `AI_INSIGHT_` and nested keys via `__`

Use `.env.example` as the canonical template for local `.env` files.

## Environment Variables Reference

Each variable below lists accepted values, default behavior, and usage.

### Runtime Environment

- `FACIS_ENV`
  - Accepted values: any environment name that maps to `config/<value>.yaml`.
  - Default: `development`.
  - Used for: selecting environment-specific YAML overrides.

### HTTP Server

- `AI_INSIGHT_HTTP__HOST`
  - Accepted values: valid bind address (`0.0.0.0`, `127.0.0.1`, etc.).
  - Default: `0.0.0.0`.
  - Used for: API server bind host.
- `AI_INSIGHT_HTTP__PORT`
  - Accepted values: integer `1..65535`.
  - Default: `8080`.
  - Used for: API server bind port.

### Service Metadata

- `AI_INSIGHT_SERVICE__NAME`
  - Accepted values: non-empty string.
  - Default: `ai-insight-service`.
  - Used for: service identity in responses/logging context.
- `AI_INSIGHT_SERVICE__ENVIRONMENT`
  - Accepted values: non-empty string (`development`, `test`, `production`, etc.).
  - Default: `development`.
  - Used for: runtime environment semantics (for example dev-only error metadata behavior).

### Logging

- `AI_INSIGHT_LOGGING__LEVEL`
  - Accepted values: standard levels (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).
  - Default: `INFO`.
  - Used for: logger verbosity.
- `AI_INSIGHT_LOGGING__FORMAT`
  - Accepted values: Python logging format string.
  - Default: `%(asctime)s - %(name)s - %(levelname)s - %(message)s`.
  - Used for: log line formatting.

### OpenAI Client

- `AI_INSIGHT_OPENAI__API_KEY`
  - Accepted values: provider API key string (nullable).
  - Default: empty/null.
  - Used for: authenticating OpenAI-compatible API calls.
- `AI_INSIGHT_OPENAI__MODEL`
  - Accepted values: provider model id (for example `gpt-4.1-mini`).
  - Default: `gpt-4.1-mini`.
  - Used for: selecting LLM model for chat completions.
- `AI_INSIGHT_OPENAI__BASE_URL`
  - Accepted values: HTTPS URL for OpenAI-compatible endpoint.
  - Default: empty/null (provider SDK default).
  - Used for: routing requests to non-default compatible backends.
- `AI_INSIGHT_OPENAI__TIMEOUT_SECONDS`
  - Accepted values: integer `1..300`.
  - Default: `30`.
  - Used for: per-request timeout to LLM backend.
- `AI_INSIGHT_OPENAI__MAX_RETRIES`
  - Accepted values: integer `0..10`.
  - Default: `3`.
  - Used for: retry count on retryable LLM failures.
- `AI_INSIGHT_OPENAI__RETRY_BASE_DELAY_SECONDS`
  - Accepted values: number `>0` and `<=10`.
  - Default: `0.5`.
  - Used for: backoff base delay.
- `AI_INSIGHT_OPENAI__RETRY_MAX_DELAY_SECONDS`
  - Accepted values: number `>0` and `<=60`.
  - Default: `8.0`.
  - Used for: cap for backoff delay.
- `AI_INSIGHT_OPENAI__REQUIRE_HTTPS`
  - Accepted values: boolean (`true/false/1/0/yes/no/on/off`).
  - Default: `true`.
  - Used for: rejecting insecure non-HTTPS OpenAI base URLs.

### Trino Connection and OIDC Auth

- `AI_INSIGHT_TRINO__HOST`
  - Accepted values: hostname or IP.
  - Default: `localhost`.
  - Used for: Trino coordinator address.
- `AI_INSIGHT_TRINO__PORT`
  - Accepted values: integer `1..65535`.
  - Default: `8080`.
  - Used for: Trino coordinator port.
- `AI_INSIGHT_TRINO__USER`
  - Accepted values: non-empty string.
  - Default: `trino`.
  - Used for: Trino user/session identity.
- `AI_INSIGHT_TRINO__OIDC_TOKEN_URL`
  - Accepted values: HTTPS token endpoint URL.
  - Default: empty/null.
  - Used for: Keycloak/OIDC password-flow token exchange.
- `AI_INSIGHT_TRINO__OIDC_CLIENT_ID`
  - Accepted values: non-empty string.
  - Default: empty/null.
  - Used for: OIDC client id.
- `AI_INSIGHT_TRINO__OIDC_CLIENT_SECRET`
  - Accepted values: non-empty string.
  - Default: empty/null.
  - Used for: OIDC client secret.
- `AI_INSIGHT_TRINO__OIDC_USERNAME`
  - Accepted values: non-empty string.
  - Default: empty/null.
  - Used for: OIDC password-flow username.
- `AI_INSIGHT_TRINO__OIDC_PASSWORD`
  - Accepted values: non-empty string.
  - Default: empty/null.
  - Used for: OIDC password-flow password.
- `AI_INSIGHT_TRINO__OIDC_SCOPE`
  - Accepted values: scope string (commonly `openid`).
  - Default: `openid`.
  - Used for: requested OIDC scopes in token exchange.
- `AI_INSIGHT_TRINO__OIDC_VERIFY`
  - Accepted values: boolean or CA bundle path.
  - Default: `true`.
  - Used for: TLS verification behavior for OIDC token endpoint calls only.
- `AI_INSIGHT_TRINO__HTTP_SCHEME`
  - Accepted values: `http` or `https`.
  - Default: `http`.
  - Used for: protocol used by Trino DBAPI client.
- `AI_INSIGHT_TRINO__VERIFY`
  - Accepted values: boolean or CA bundle path.
  - Default: `true`.
  - Used for: TLS verification behavior for Trino HTTPS requests.
- `AI_INSIGHT_TRINO__REQUEST_TIMEOUT_SECONDS`
  - Accepted values: integer `1..300`.
  - Default: `120`.
  - Used for: Trino request timeout.
- `AI_INSIGHT_TRINO__CATALOG`
  - Accepted values: existing Trino catalog name.
  - Default: `hive`.
  - Used for: Trino catalog in sessions/queries.
- `AI_INSIGHT_TRINO__SCHEMA`
  - Accepted values: schema name string.
  - Default: `default`.
  - Used for: default Trino session schema.
- `AI_INSIGHT_TRINO__TARGET_SCHEMA`
  - Accepted values: schema containing analytics views/tables.
  - Default: `gold`.
  - Used for: fully qualified source table resolution in analytics queries.
- `AI_INSIGHT_TRINO__TABLE_NET_GRID_HOURLY`
  - Accepted values: table/view name.
  - Default: `net_grid_hourly`.
  - Used for: net-grid base dataset source.
- `AI_INSIGHT_TRINO__TABLE_EVENT_IMPACT_DAILY`
  - Accepted values: table/view name.
  - Default: `event_impact_daily`.
  - Used for: event impact source in city-status pipeline.
- `AI_INSIGHT_TRINO__TABLE_STREETLIGHT_ZONE_HOURLY`
  - Accepted values: table/view name.
  - Default: `streetlight_zone_hourly`.
  - Used for: streetlight source in city-status pipeline.
- `AI_INSIGHT_TRINO__TABLE_WEATHER_HOURLY`
  - Accepted values: table/view name.
  - Default: `weather_hourly`.
  - Used for: weather source in energy-summary pipeline.
- `AI_INSIGHT_TRINO__TABLE_ENERGY_COST_DAILY`
  - Accepted values: table/view name.
  - Default: `energy_cost_daily`.
  - Used for: daily cost source in energy-summary pipeline.
- `AI_INSIGHT_TRINO__TABLE_PV_SELF_CONSUMPTION_DAILY`
  - Accepted values: table/view name.
  - Default: `pv_self_consumption_daily`.
  - Used for: daily PV self-consumption source in energy-summary pipeline.

### Policy Enforcement

- `AI_INSIGHT_POLICY__ENABLED`
  - Accepted values: boolean.
  - Default: `true`.
  - Used for: turning request policy checks on/off.
- `AI_INSIGHT_POLICY__AGREEMENT_HEADER`
  - Accepted values: header name string.
  - Default: `x-agreement-id`.
  - Used for: identifying agreement header key.
- `AI_INSIGHT_POLICY__ASSET_HEADER`
  - Accepted values: header name string.
  - Default: `x-asset-id`.
  - Used for: identifying asset header key.
- `AI_INSIGHT_POLICY__ROLE_HEADER`
  - Accepted values: header name string.
  - Default: `x-user-roles`.
  - Used for: identifying roles header key.
- `AI_INSIGHT_POLICY__REQUIRED_ROLES`
  - Accepted values: JSON array of strings.
  - Default: `["ai_insight_consumer"]`.
  - Used for: roles required for access.
- `AI_INSIGHT_POLICY__ALLOWED_AGREEMENT_IDS`
  - Accepted values: JSON array of strings.
  - Default: `[]` (no explicit allow-list restriction).
  - Used for: optional agreement allow-list.
- `AI_INSIGHT_POLICY__ALLOWED_ASSET_IDS`
  - Accepted values: JSON array of strings.
  - Default: `[]` (no explicit allow-list restriction).
  - Used for: optional asset allow-list.

### Rate Limiting

- `AI_INSIGHT_RATE_LIMIT__ENABLED`
  - Accepted values: boolean.
  - Default: `true`.
  - Used for: toggling agreement-scoped rate limiting.
- `AI_INSIGHT_RATE_LIMIT__REQUESTS_PER_MINUTE`
  - Accepted values: integer `1..10000`.
  - Default: `10`.
  - Used for: allowed requests per minute per agreement.

### Cache

- `AI_INSIGHT_CACHE__ENABLED`
  - Accepted values: boolean.
  - Default: `false`.
  - Used for: enabling/disabling insight response cache.
- `AI_INSIGHT_CACHE__BACKEND`
  - Accepted values: backend identifier string (`redis` supported).
  - Default: `redis`.
  - Used for: selecting cache implementation.
- `AI_INSIGHT_CACHE__REDIS_URL`
  - Accepted values: Redis URL (`redis://...`) or empty when disabled.
  - Default: empty/null.
  - Used for: Redis connection endpoint.
- `AI_INSIGHT_CACHE__TTL_SECONDS`
  - Accepted values: integer `1..86400`.
  - Default: `300`.
  - Used for: cache entry expiration.
- `AI_INSIGHT_CACHE__KEY_PREFIX`
  - Accepted values: non-empty string.
  - Default: `ai-insight:cache:v1`.
  - Used for: key namespace isolation.
- `AI_INSIGHT_CACHE__CONNECT_TIMEOUT_SECONDS`
  - Accepted values: number `>0` and `<=30`.
  - Default: `1.0`.
  - Used for: Redis client connect timeout.

### Audit Logging

- `AI_INSIGHT_AUDIT__ENABLED`
  - Accepted values: boolean.
  - Default: `true`.
  - Used for: enabling/disabling audit events.
- `AI_INSIGHT_AUDIT__LOG_PROMPTS`
  - Accepted values: boolean.
  - Default: `true`.
  - Used for: controlling whether LLM prompts are logged.
- `AI_INSIGHT_AUDIT__LOG_RESPONSES`
  - Accepted values: boolean.
  - Default: `true`.
  - Used for: controlling whether LLM responses are logged.
- `AI_INSIGHT_AUDIT__LOGGER_NAME`
  - Accepted values: logger name string.
  - Default: `src.audit`.
  - Used for: selecting the Python logger namespace for audit output.

### Prompt Templates

- `AI_INSIGHT_PROMPT_TEMPLATES__ENABLED`
  - Accepted values: boolean.
  - Default: `false`.
  - Used for: enabling external prompt templates from filesystem.
- `AI_INSIGHT_PROMPT_TEMPLATES__PATH`
  - Accepted values: valid directory path.
  - Default: `/app/config/prompts`.
  - Used for: location of mounted prompt template files.

## OpenAPI Source of Truth

OpenAPI spec lives in `docs/openapi.yaml` and is served at runtime:

- `/openapi.json`
- `/docs`
- `/redoc`

## Runtime Behavior Notes

- Requests are policy checked (`403` on denied access).
- Agreement-scoped throttling returns `429` when exceeded.
- Trino reads use OIDC password-flow JWT auth.
- Repeated identical requests can be served from cache.
- LLM calls use retry and fallback to rule-based output when needed.

## Project Structure

```text
ai-insight-service/
├── config/
├── tests/
├── src/
│   ├── analytics/
│   ├── api/rest/
│   ├── data/
│   ├── llm/
│   ├── services/
│   ├── config.py
│   └── main.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```
