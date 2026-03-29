# Architecture Guide

## Overview

AI Insight Service provides governed REST endpoints to produce three insight types:

- `anomaly-report`
- `city-status`
- `energy-summary`

Each request builds deterministic analytics context from Trino, optionally enriches it
through a provider-agnostic chat-completions model, and returns structured output.

## Request Flow

1. Validate request payload and time window.
2. Build access context from headers (`agreement`, `asset`, `roles`).
3. Enforce policy rules and rate limits.
4. Query Trino datasets for the selected insight pipeline.
5. Build analytics context and compose LLM prompt.
6. Call configured chat-completions endpoint with retries.
7. If LLM fails or output is invalid, use deterministic fallback summary.
8. Persist output metadata, update latest snapshot, optionally cache result.

## Core Components

| Area | Path | Responsibility |
|---|---|---|
| API layer | `src/api/rest/` | FastAPI app, routes, request/response models |
| Analytics | `src/analytics/` | Outlier detection, correlation logic, forecasting primitives |
| Data access | `src/data/trino_client.py` | Trino connectivity and OIDC token flow |
| LLM client/context | `src/llm/` | Prompt templates, context builder, model integration |
| Orchestration | `src/services/` | Pipeline orchestration for each insight type |
| Security | `src/security/` | Policy enforcement and in-memory rate limiting |
| Storage | `src/storage/` | Cache abstraction and output store |

## Data Sources

The service reads from Trino Gold datasets (default schema `gold`):

- `net_grid_hourly`
- `event_impact_daily`
- `streetlight_zone_hourly`
- `weather_hourly`
- `energy_cost_daily`
- `pv_self_consumption_daily`

Names are configurable via `AI_INSIGHT_TRINO__TABLE_*` variables.

## Runtime Behavior Notes

- Policy denial returns `403`.
- Rate-limit denial returns `429` and `retry-after`.
- Upstream query/auth failures return `502`.
- Validation errors return `422` (or `400` for invalid time windows).
- In development/test scenarios, fallback metadata can include `llm_error`.

## Deployment Topology (Local)

- `ai-insight` container (FastAPI + service runtime)
- optional `redis` container for cache backend
- external Trino and OIDC provider (not bundled in this service)
