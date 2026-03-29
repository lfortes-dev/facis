# Configuration Guide

## Layered Configuration Model

Configuration is resolved in this order (later entries override earlier entries):

1. `config/default.yaml`
2. `config/{FACIS_ENV}.yaml` (for example: `development`, `test`, `production`)
3. Environment variables prefixed with `AI_INSIGHT_` using `__` as nested separator

Example:

- `AI_INSIGHT_TRINO__HOST` -> `trino.host`
- `AI_INSIGHT_RATE_LIMIT__REQUESTS_PER_MINUTE` -> `rate_limit.requests_per_minute`

## Baseline Defaults

Important defaults from `config/default.yaml`:

| Key | Default |
|---|---|
| `http.host` | `0.0.0.0` |
| `http.port` | `8080` |
| `llm.model` | `gpt-4.1-mini` |
| `trino.catalog` | `hive` |
| `trino.target_schema` | `gold` |
| `policy.enabled` | `true` |
| `rate_limit.enabled` | `true` |
| `rate_limit.requests_per_minute` | `10` |
| `cache.enabled` | `false` |
| `audit.enabled` | `true` |

## Key Environment Variable Groups

### Runtime

- `FACIS_ENV`

### HTTP

- `AI_INSIGHT_HTTP__HOST`
- `AI_INSIGHT_HTTP__PORT`

### LLM Provider

- `AI_INSIGHT_LLM__API_KEY`
- `AI_INSIGHT_LLM__MODEL`
- `AI_INSIGHT_LLM__CHAT_COMPLETIONS_URL`
- `AI_INSIGHT_LLM__TIMEOUT_SECONDS`
- `AI_INSIGHT_LLM__MAX_RETRIES`
- `AI_INSIGHT_LLM__RETRY_BASE_DELAY_SECONDS`
- `AI_INSIGHT_LLM__RETRY_MAX_DELAY_SECONDS`
- `AI_INSIGHT_LLM__REQUIRE_HTTPS`

### Trino and OIDC

- `AI_INSIGHT_TRINO__HOST`
- `AI_INSIGHT_TRINO__PORT`
- `AI_INSIGHT_TRINO__USER`
- `AI_INSIGHT_TRINO__OIDC_TOKEN_URL`
- `AI_INSIGHT_TRINO__OIDC_CLIENT_ID`
- `AI_INSIGHT_TRINO__OIDC_CLIENT_SECRET`
- `AI_INSIGHT_TRINO__OIDC_USERNAME`
- `AI_INSIGHT_TRINO__OIDC_PASSWORD`
- `AI_INSIGHT_TRINO__OIDC_SCOPE`
- `AI_INSIGHT_TRINO__OIDC_VERIFY`
- `AI_INSIGHT_TRINO__VERIFY`
- `AI_INSIGHT_TRINO__REQUEST_TIMEOUT_SECONDS`
- `AI_INSIGHT_TRINO__CATALOG`
- `AI_INSIGHT_TRINO__SCHEMA`
- `AI_INSIGHT_TRINO__TARGET_SCHEMA`
- `AI_INSIGHT_TRINO__TABLE_*`

### Policy and Rate Limiting

- `AI_INSIGHT_POLICY__ENABLED`
- `AI_INSIGHT_POLICY__AGREEMENT_HEADER`
- `AI_INSIGHT_POLICY__ASSET_HEADER`
- `AI_INSIGHT_POLICY__ROLE_HEADER`
- `AI_INSIGHT_POLICY__REQUIRED_ROLES`
- `AI_INSIGHT_POLICY__ALLOWED_AGREEMENT_IDS`
- `AI_INSIGHT_POLICY__ALLOWED_ASSET_IDS`
- `AI_INSIGHT_RATE_LIMIT__ENABLED`
- `AI_INSIGHT_RATE_LIMIT__REQUESTS_PER_MINUTE`

### Cache and Audit

- `AI_INSIGHT_CACHE__ENABLED`
- `AI_INSIGHT_CACHE__BACKEND`
- `AI_INSIGHT_CACHE__REDIS_URL`
- `AI_INSIGHT_CACHE__TTL_SECONDS`
- `AI_INSIGHT_CACHE__KEY_PREFIX`
- `AI_INSIGHT_AUDIT__ENABLED`
- `AI_INSIGHT_AUDIT__LOGGER_NAME`

## Secure Configuration Recommendations

- Keep OIDC client secret, user credentials, and API keys in secret stores.
- Use HTTPS endpoints for LLM provider URLs and Trino in non-local environments.
- Keep policy and rate-limiting enabled outside local debugging.
- Disable audit prompt/response logging where policy requires reduced data retention.

## Reference Files

- `config/default.yaml`
- `config/development.yaml`
- `config/test.yaml`
- `config/production.yaml`
- `.env.example`
