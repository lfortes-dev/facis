# FACIS AI Insight Service

FastAPI service for AI-powered insights in the FACIS IoT & AI demonstrator.

## Quick Start

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
pip install -e .
python -m src.main
```

Service health endpoint:

```bash
curl http://localhost:8080/api/v1/health
```

API documentation:

```bash
# Swagger UI
http://localhost:8080/docs

# ReDoc
http://localhost:8080/redoc
```

## Run with Docker Compose

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
docker compose up --build
```

To stop:

```bash
docker compose down
```

## Testing

Install dev dependencies and run tests:

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
pip install -e ".[dev]"
python -m pytest -v
```

Run lint:

```bash
python -m ruff check src tests
```

## Configuration

Configuration is loaded from:

1. `config/default.yaml`
2. `config/{FACIS_ENV}.yaml` (default `development`)
3. Environment variables with prefix `AI_INSIGHT_` and nested delimiter `__`

Environment template:

- `.env.example` (copy to `.env` for local development)

Examples:

- `AI_INSIGHT_OPENAI__API_KEY=...`
- `AI_INSIGHT_OPENAI__MODEL=gpt-4.1-mini`
- `AI_INSIGHT_TRINO__HOST=trino`
- `AI_INSIGHT_HTTP__PORT=8080`

For Trino-backed outlier analysis, also set:

- `AI_INSIGHT_TRINO__PORT=8080`
- `AI_INSIGHT_TRINO__USER=trino`
- `AI_INSIGHT_TRINO__CATALOG=hive`
- `AI_INSIGHT_TRINO__SCHEMA=default`
- `AI_INSIGHT_TRINO__HTTP_SCHEME=https`
- `AI_INSIGHT_TRINO__VERIFY=true` (or CA bundle path, e.g. `/app/certs/trino-ca.crt`)

Authentication behavior:

- if `AI_INSIGHT_TRINO__OIDC_TOKEN_URL` is **empty**: service connects to Trino without token auth
- if `AI_INSIGHT_TRINO__OIDC_TOKEN_URL` is **set**: service performs Keycloak password-flow token exchange and uses JWT auth for Trino

For Keycloak password-flow token exchange (JWT to Trino):

- `AI_INSIGHT_TRINO__OIDC_TOKEN_URL=.../protocol/openid-connect/token`
- `AI_INSIGHT_TRINO__OIDC_CLIENT_ID=...`
- `AI_INSIGHT_TRINO__OIDC_CLIENT_SECRET=...`
- `AI_INSIGHT_TRINO__OIDC_USERNAME=...`
- `AI_INSIGHT_TRINO__OIDC_PASSWORD=...`
- `AI_INSIGHT_TRINO__OIDC_SCOPE=openid`
- `AI_INSIGHT_TRINO__OIDC_VERIFY=true` (CA strategy for Keycloak HTTPS)

TLS notes:

- keep `AI_INSIGHT_TRINO__VERIFY=/app/certs/trino-ca.crt` when Trino uses self-signed/internal CA
- `AI_INSIGHT_TRINO__OIDC_VERIFY` is independent from Trino TLS and controls only Keycloak token HTTPS
- use `AI_INSIGHT_TRINO__OIDC_VERIFY=false` only as temporary workaround
- place local CA files under `certs/` (gitignored; not version-controlled)

Catalog note:

- if you get `CATALOG_NOT_FOUND`, set `AI_INSIGHT_TRINO__CATALOG` to a valid catalog available in your Trino cluster

## OpenAPI Source of Truth

OpenAPI documentation is defined in:

- `docs/openapi.yaml`

At startup, the app loads this file and serves it at:

- `/openapi.json`
- `/docs`
- `/redoc`

## Outlier Detection Notes

The endpoint uses robust z-score based on MAD (median absolute deviation):

- `robust_z = (value - median) / (1.4826 * MAD)`
- values with `|robust_z| >= robust_z_threshold` are marked as outliers
- positive values are tagged as `spike`, negative values as `drop`
- default `robust_z_threshold` is `3.5`

`robust_z_threshold` tuning:

- lower value (for example `2.5`) = more sensitive, more potential false positives
- higher value (for example `4.5`) = stricter, only stronger anomalies

The endpoint contract is maintained in OpenAPI (`docs/openapi.yaml`) and exposed at
`/openapi.json`, `/docs`, and `/redoc`.

## Prompt Templates (Internal)

The service now provides internal prompt templates to pair analytics `context` with
system guidance and strict JSON output instructions.

Example usage:

```python
from src.llm import build_prompt_payload

payload = build_prompt_payload(
    insight_type="net_grid_outliers",
    context=context,
)

system_prompt = payload["system"]
user_prompt = payload["user"]
expected_schema = payload["expected_json_schema"]
```

Required LLM output format (top-level keys only):

- `summary`: string
- `key_findings`: list of strings
- `recommendations`: list of strings

The output schema is exposed as `EXPECTED_OUTPUT_JSON_SCHEMA` in `src.llm`.

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
