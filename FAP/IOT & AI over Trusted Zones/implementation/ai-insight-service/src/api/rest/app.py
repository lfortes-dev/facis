"""FastAPI app factory for AI Insight Service."""

from fastapi import FastAPI


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="FACIS AI Insight Service",
        version="0.1.0",
        description="Service for generating AI-powered insights from energy and IoT data.",
    )

    @app.get("/api/v1/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "ai-insight-service"}

    return app
