# Setup Guide

## Local Development Setup

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
pip install -e ".[dev]"
python -m src.main
```

Service endpoints:

- API base: `http://localhost:8080`
- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`
- Health: `http://localhost:8080/api/v1/health`

## Docker Compose Setup

```bash
cd FAP/IOT\ \&\ AI\ over\ Trusted\ Zones/implementation/ai-insight-service
cp .env.example .env
docker compose up --build
```

Stop services:

```bash
docker compose down
```

## Running Tests

Run full test suite:

```bash
python -m pytest -v
```

Run BDD scenarios:

```bash
python -m pytest -v tests/bdd
```

Run integration tests:

```bash
python -m pytest -v tests/integration
```

Run lint checks:

```bash
python -m ruff check src tests
```

## Minimal Runtime Requirements

- Python 3.11+
- Trino endpoint reachable from service runtime
- OpenAI-compatible endpoint (or deterministic fallback behavior)
- Redis only when cache is enabled

## Environment Bootstrap Notes

- Copy `.env.example` and edit only values needed for your environment.
- Keep secrets out of committed files. Use environment variables or secret injection in deployment.
- The active environment profile is selected with `FACIS_ENV` (`development`, `test`, `production`).
