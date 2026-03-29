# FACIS AI Insight Service

FastAPI service for governed AI insight generation from energy and IoT datasets.

## What This Service Provides

- Governed insight endpoints (`anomaly-report`, `city-status`, `energy-summary`)
- Header-based policy checks and agreement-scoped rate limiting
- Trino-backed analytics context for deterministic insight pipelines
- OpenAI-compatible LLM summarization with rule-based fallback behavior
- Optional Redis caching and output retrieval endpoints

## Quick Start (Local)

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
pip install -e ".[dev]"
python -m src.main
```

Health check:

```bash
curl http://localhost:8080/api/v1/health
```

API docs:

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

## Documentation

- [Documentation hub](docs/README.md)
- [Developer guide](docs/guides/index.md)
- [Setup guide](docs/guides/setup.md)
- [Architecture guide](docs/guides/architecture.md)
- [Configuration guide](docs/guides/configuration.md)
- [REST API reference](docs/api/rest-api.md)
- [OpenAPI contract](docs/openapi.yaml)

## Governance and Compliance

- [SECURITY.md](SECURITY.md)
- [NOTICE.md](NOTICE.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [LICENSE](LICENSE)
