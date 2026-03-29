# REST API Reference

**Project:** FACIS FAP - IoT & AI Demonstrator  
**Service:** AI Insight Service  
**Base URL:** `http://localhost:8080`

---

## API Contract Source of Truth

The canonical API contract is maintained in:

- `docs/openapi.yaml`

Runtime documentation endpoints:

- `GET /openapi.json`
- `GET /docs`
- `GET /redoc`

## Main Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/health` | GET | Service health status |
| `/api/v1/insights/anomaly-report` | POST | Net-grid anomaly insight generation |
| `/api/v1/insights/city-status` | POST | Smart-city event impact insight generation |
| `/api/v1/insights/energy-summary` | POST | Energy trend and forecast insight generation |
| `/api/v1/insights/latest` | GET | Latest per-type generated outputs |
| `/api/ai/outputs/{output_id}` | GET | Fetch persisted output by id |

## Governance and Access

Insight endpoints are governed by header-based policy and rate limiting.

Required headers (default names):

- `x-agreement-id`
- `x-asset-id`
- `x-user-roles`

Typical responses:

- `200` success
- `400` invalid time window
- `403` policy denied
- `422` validation error
- `429` rate limit exceeded
- `502` upstream processing/query failure

## Example Request

```bash
curl -X POST http://localhost:8080/api/v1/insights/energy-summary \
  -H "x-agreement-id: agreement-1" \
  -H "x-asset-id: asset-7" \
  -H "x-user-roles: ai_insight_consumer" \
  -H "Content-Type: application/json" \
  -d '{
    "start_ts": "2026-03-01T00:00:00Z",
    "end_ts": "2026-03-02T00:00:00Z",
    "timezone": "UTC",
    "forecast_alpha": 0.6,
    "trend_epsilon": 0.02,
    "daily_overview_strategy": "strict_daily"
  }'
```

## Notes

- Request windows must satisfy `start_ts < end_ts`.
- `include_data=true` returns analytics context under `data`.
- On LLM failure or invalid output, the service can fall back to deterministic summaries.
