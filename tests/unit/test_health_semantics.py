"""Tests for Section B: Backend API — health semantics, startup, Swagger.

Covers:
  B1) API starts and responds
  B2) Health endpoint semantics (/health, /health/live, /health/ready)
  B3) Swagger available in development mode
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fittrack.core.config import Settings
from fittrack.main import create_app


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def dev_app() -> Any:
    """App in development mode (no DB pool)."""
    settings = Settings(app_env="development")
    application = create_app(settings=settings)
    return application


@pytest.fixture
def dev_client(dev_app: Any) -> TestClient:
    return TestClient(dev_app)


@pytest.fixture
def prod_app() -> Any:
    """App in production mode (no DB pool)."""
    settings = Settings(app_env="production")
    application = create_app(settings=settings)
    return application


@pytest.fixture
def prod_client(prod_app: Any) -> TestClient:
    return TestClient(prod_app)


@pytest.fixture
def app_with_healthy_db() -> Any:
    """App with a mock DB pool that responds to queries."""
    settings = Settings(app_env="development")
    application = create_app(settings=settings)

    # Mock a healthy DB pool
    mock_cursor = MagicMock()
    mock_cursor.execute = MagicMock()
    mock_cursor.fetchone = MagicMock(return_value=(1,))
    mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
    mock_cursor.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_conn.close = MagicMock()

    mock_pool = MagicMock()
    mock_pool.acquire.return_value = mock_conn

    application.state.db_pool = mock_pool
    return application


@pytest.fixture
def client_with_db(app_with_healthy_db: Any) -> TestClient:
    return TestClient(app_with_healthy_db)


@pytest.fixture
def app_with_broken_db() -> Any:
    """App with a mock DB pool that raises on query."""
    settings = Settings(app_env="production")
    application = create_app(settings=settings)

    mock_pool = MagicMock()
    mock_pool.acquire.side_effect = Exception("Connection refused")

    application.state.db_pool = mock_pool
    return application


@pytest.fixture
def client_with_broken_db(app_with_broken_db: Any) -> TestClient:
    return TestClient(app_with_broken_db)


# ── B1: API Startup ─────────────────────────────────────────────────


class TestB1ApiStartup:
    """B1) API starts and responds to basic requests."""

    def test_dev_app_starts_without_db(self, dev_client: TestClient) -> None:
        """API in dev mode starts even without Oracle database."""
        resp = dev_client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_health_returns_environment(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/health")
        assert resp.json()["environment"] == "development"

    def test_health_shows_db_disconnected_without_pool(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/health")
        assert resp.json()["database"] == "disconnected"

    def test_health_shows_db_connected_with_pool(self, client_with_db: TestClient) -> None:
        resp = client_with_db.get("/health")
        assert resp.json()["database"] == "connected"


# ── B2: Health Endpoint Semantics ────────────────────────────────────


class TestB2HealthSemantics:
    """B2) Health endpoints have correct Kubernetes probe semantics."""

    # -- /health/live: always 200 if process is alive --

    def test_liveness_200_without_db(self, dev_client: TestClient) -> None:
        """/health/live returns 200 regardless of DB state."""
        resp = dev_client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_liveness_200_with_db(self, client_with_db: TestClient) -> None:
        resp = client_with_db.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_liveness_no_db_dependency(self, prod_client: TestClient) -> None:
        """/health/live in production mode still returns 200 without DB."""
        resp = prod_client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    # -- /health/ready: depends on DB --

    def test_readiness_200_when_db_healthy(self, client_with_db: TestClient) -> None:
        """/health/ready returns 200 when DB responds to SELECT 1."""
        resp = client_with_db.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"]["status"] == "ok"
        assert "response_time_ms" in data["checks"]["database"]

    def test_readiness_503_when_db_broken(self, client_with_broken_db: TestClient) -> None:
        """/health/ready returns 503 when DB connection fails."""
        resp = client_with_broken_db.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert data["checks"]["database"]["status"] == "error"

    def test_readiness_dev_no_db_is_still_ready(self, dev_client: TestClient) -> None:
        """In dev mode, missing DB pool doesn't make us unready (graceful degradation)."""
        resp = dev_client.get("/health/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["checks"]["database"]["status"] == "not_configured"

    def test_readiness_prod_no_db_is_not_ready(self, prod_client: TestClient) -> None:
        """In production, missing DB pool means not ready (503)."""
        resp = prod_client.get("/health/ready")
        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"


# ── B3: Swagger Available in Dev ─────────────────────────────────────


class TestB3SwaggerDev:
    """B3) /docs Swagger UI available in development mode."""

    def test_docs_available_in_dev(self, dev_client: TestClient) -> None:
        """GET /docs loads Swagger UI in development mode."""
        resp = dev_client.get("/docs")
        assert resp.status_code == 200
        assert "swagger" in resp.text.lower()

    def test_redoc_available_in_dev(self, dev_client: TestClient) -> None:
        """GET /redoc also available."""
        resp = dev_client.get("/redoc")
        assert resp.status_code == 200

    def test_openapi_json_available(self, dev_client: TestClient) -> None:
        """OpenAPI JSON schema is served."""
        resp = dev_client.get("/openapi.json")
        assert resp.status_code == 200
        data = resp.json()
        assert "paths" in data
        assert len(data["paths"]) > 50  # we have ~76 paths
