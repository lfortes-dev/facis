"""FastAPI app factory for AI Insight Service."""

import logging
from pathlib import Path

import yaml
from fastapi import FastAPI

from src.api.rest.routes.insights import insights_router, outputs_router

logger = logging.getLogger(__name__)

# docs/openapi.yaml relative to project root (parent of src/)
_OPENAPI_SPEC = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "openapi.yaml"


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    @app.get("/api/v1/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "ai-insight-service"}

    app.include_router(insights_router)
    app.include_router(outputs_router)

    if _OPENAPI_SPEC.exists():
        with open(_OPENAPI_SPEC, encoding="utf-8") as file:
            app.openapi_schema = yaml.safe_load(file)
    else:
        logger.warning(
            "OpenAPI spec file not found at %s. Falling back to auto-generated schema.",
            _OPENAPI_SPEC,
        )

    return app
