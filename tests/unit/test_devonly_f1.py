"""Checkpoint F — Dev-only features gating tests.

Verifies that /api/v1/dev/* endpoints and static test page are
available in development but return 404 in production.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def dev_client(patch_db_pool) -> TestClient:
    """TestClient running in development mode."""
    from fittrack.core.config import Settings
    from fittrack.main import create_app

    app = create_app(settings=Settings(app_env="development"))
    return TestClient(app)


@pytest.fixture()
def prod_client(patch_db_pool) -> TestClient:
    """TestClient running in production mode."""
    from fittrack.core.config import Settings
    from fittrack.main import create_app

    app = create_app(settings=Settings(app_env="production"))
    return TestClient(app)


# ── F1: Dev endpoints in development ────────────────────────────────


class TestF1DevAvailable:
    """Dev-only endpoints are accessible when APP_ENV=development."""

    def test_dev_seed_available(self, dev_client: TestClient) -> None:
        resp = dev_client.post("/api/v1/dev/seed")
        # Should succeed (or mock-respond) — not 404
        assert resp.status_code != 404

    def test_dev_reset_available(self, dev_client: TestClient) -> None:
        resp = dev_client.post("/api/v1/dev/reset")
        assert resp.status_code != 404

    def test_dev_migrate_available(self, dev_client: TestClient) -> None:
        resp = dev_client.post("/api/v1/dev/migrate")
        assert resp.status_code != 404

    def test_dev_tables_available(self, dev_client: TestClient) -> None:
        resp = dev_client.get("/api/v1/dev/tables")
        assert resp.status_code != 404

    def test_static_test_page_mounted(self, dev_client: TestClient) -> None:
        """Static mount exists in dev (may 404 if file missing, but route exists)."""
        dev_client.get("/static/test_page.html")
        # In a test environment without the static dir, this may be 404 from
        # StaticFiles or 200 if the file exists. The key is that the mount
        # is created at all (not stripped out).
        # We verify by checking the app has a route named "static"
        routes = [r.name for r in dev_client.app.routes]  # type: ignore[union-attr]
        assert "static" in routes


# ── F1: Dev endpoints in production ─────────────────────────────────


class TestF1ProdBlocked:
    """Dev-only endpoints return 404 when APP_ENV=production."""

    def test_dev_seed_blocked(self, prod_client: TestClient) -> None:
        resp = prod_client.post("/api/v1/dev/seed")
        assert resp.status_code == 404

    def test_dev_reset_blocked(self, prod_client: TestClient) -> None:
        resp = prod_client.post("/api/v1/dev/reset")
        assert resp.status_code == 404

    def test_dev_migrate_blocked(self, prod_client: TestClient) -> None:
        resp = prod_client.post("/api/v1/dev/migrate")
        assert resp.status_code == 404

    def test_dev_tables_blocked(self, prod_client: TestClient) -> None:
        resp = prod_client.get("/api/v1/dev/tables")
        assert resp.status_code == 404

    def test_static_test_page_not_mounted(self, prod_client: TestClient) -> None:
        """Static file mount should not exist in production."""
        routes = [r.name for r in prod_client.app.routes]  # type: ignore[union-attr]
        assert "static" not in routes


# ── F1: Testing environment behaves like dev ────────────────────────


class TestF1TestingEnv:
    """In testing mode, dev endpoints should be accessible (like dev)."""

    def test_dev_seed_in_testing(self, client: TestClient) -> None:
        resp = client.post("/api/v1/dev/seed")
        assert resp.status_code != 404

    def test_dev_tables_in_testing(self, client: TestClient) -> None:
        resp = client.get("/api/v1/dev/tables")
        assert resp.status_code != 404
