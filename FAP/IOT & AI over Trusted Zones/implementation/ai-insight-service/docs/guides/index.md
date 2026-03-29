# FACIS AI Insight Service - Developer Guide

**Project:** FACIS FAP - IoT & AI Demonstrator  
**Service:** AI Insight Service

---

## What Is This?

The AI Insight Service is a FastAPI application that creates governed insights from
energy and smart-city datasets. It combines:

- Trino-backed analytics context extraction
- Header-based policy and agreement-scoped rate limiting
- OpenAI-compatible LLM summarization with deterministic fallback
- Optional Redis caching for repeated requests

## Quickstart

Prerequisites: Python 3.11+, pip.

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
pip install -e ".[dev]"
python -m src.main
```

Check service health:

```bash
curl http://localhost:8080/api/v1/health
```

## Guide Contents

| Document | Description |
|---|---|
| [setup.md](setup.md) | Local setup, Docker startup, testing commands |
| [architecture.md](architecture.md) | Components, request flow, runtime behavior |
| [configuration.md](configuration.md) | Layered config model and key environment variables |

## Related Documentation

| Document | Path | Description |
|---|---|---|
| Docs hub | [`../README.md`](../README.md) | Documentation structure and conventions |
| REST API guide | [`../api/rest-api.md`](../api/rest-api.md) | Endpoint-level usage and behavior notes |
| OpenAPI contract | [`../openapi.yaml`](../openapi.yaml) | Formal API source of truth |
| Security policy | [`../../SECURITY.md`](../../SECURITY.md) | Vulnerability reporting and support policy |
| Notice file | [`../../NOTICE.md`](../../NOTICE.md) | Third-party and project attribution notice |

---

Copyright (c) 2025-2026 ATLAS IoT Lab GmbH.
Licensed under Apache License 2.0.
