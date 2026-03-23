"""Pytest fixtures for AI Insight Service tests."""

import pytest
from fastapi.testclient import TestClient

from src.api.rest.app import create_app


@pytest.fixture
def app():
    """FastAPI app fixture."""
    return create_app()


@pytest.fixture
def client():
    """HTTP test client fixture."""
    return TestClient(create_app())
