# FACIS AI Insight Service

FastAPI scaffold for AI-powered insight generation in the FACIS IoT & AI demonstrator.

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

## Project Structure

```text
ai-insight-service/
├── config/
├── src/
│   ├── api/rest/app.py
│   ├── config.py
│   └── main.py
├── .env.example
├── docker-compose.yml
├── Dockerfile
└── pyproject.toml
```
