"""Tests for RBAC (role-based access control) dependencies."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from fittrack.api.deps import (
    get_current_user,
    get_current_user_id,
    require_admin,
    require_role,
)
from fittrack.core.security import create_access_token, create_refresh_token

# ── Helper app for testing dependencies in isolation ─────────────────


def _make_test_app() -> FastAPI:
    """Build a minimal FastAPI app with test endpoints."""
    app = FastAPI()

    @app.get("/public")
    def public_endpoint() -> dict[str, str]:
        return {"access": "public"}

    @app.get("/protected")
    def protected_endpoint(
        user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        return {"user_id": user["sub"], "role": user["role"]}

    @app.get("/admin-only")
    def admin_endpoint(
        user: dict[str, Any] = Depends(require_admin),
    ) -> dict[str, Any]:
        return {"admin": True, "user_id": user["sub"]}

    @app.get("/premium-or-admin")
    def premium_admin_endpoint(
        user: dict[str, Any] = Depends(require_role("premium", "admin")),
    ) -> dict[str, Any]:
        return {"role": user["role"]}

    @app.get("/user-id")
    def user_id_endpoint(
        uid: str = Depends(get_current_user_id),
    ) -> dict[str, str]:
        return {"user_id": uid}

    return app


@pytest.fixture
def rbac_client() -> TestClient:
    return TestClient(_make_test_app())


# ── Tests ────────────────────────────────────────────────────────────


class TestGetCurrentUser:
    """get_current_user dependency."""

    def test_no_auth_header(self, rbac_client: TestClient) -> None:
        resp = rbac_client.get("/protected")
        assert resp.status_code == 401
        assert "Missing Authorization" in resp.json()["detail"]

    def test_bad_auth_format(self, rbac_client: TestClient) -> None:
        resp = rbac_client.get(
            "/protected",
            headers={"Authorization": "Basic abc123"},
        )
        assert resp.status_code == 401
        assert "Invalid Authorization" in resp.json()["detail"]

    def test_invalid_token(self, rbac_client: TestClient) -> None:
        resp = rbac_client.get(
            "/protected",
            headers={"Authorization": "Bearer bad.token.value"},
        )
        assert resp.status_code == 401

    def test_refresh_token_rejected(self, rbac_client: TestClient) -> None:
        token = create_refresh_token(subject="uid1", session_id="sid1")
        resp = rbac_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 401
        assert "Invalid token type" in resp.json()["detail"]

    def test_valid_access_token(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="uid1", role="user")
        resp = rbac_client.get(
            "/protected",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "uid1"
        assert data["role"] == "user"

    def test_public_endpoint_no_auth_needed(self, rbac_client: TestClient) -> None:
        resp = rbac_client.get("/public")
        assert resp.status_code == 200


class TestRequireAdmin:
    """require_admin dependency."""

    def test_admin_allowed(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="admin1", role="admin")
        resp = rbac_client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["admin"] is True

    def test_user_denied(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="uid1", role="user")
        resp = rbac_client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Admin access required" in resp.json()["detail"]

    def test_premium_denied(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="prem1", role="premium")
        resp = rbac_client.get(
            "/admin-only",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403


class TestRequireRole:
    """require_role dependency factory."""

    def test_matching_role_allowed(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="prem1", role="premium")
        resp = rbac_client.get(
            "/premium-or-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_admin_also_allowed(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="admin1", role="admin")
        resp = rbac_client.get(
            "/premium-or-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200

    def test_user_role_denied(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="uid1", role="user")
        resp = rbac_client.get(
            "/premium-or-admin",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
        assert "Insufficient permissions" in resp.json()["detail"]


class TestGetCurrentUserId:
    """get_current_user_id dependency."""

    def test_extracts_user_id(self, rbac_client: TestClient) -> None:
        token = create_access_token(subject="myuid", role="user")
        resp = rbac_client.get(
            "/user-id",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["user_id"] == "myuid"

    def test_missing_token(self, rbac_client: TestClient) -> None:
        resp = rbac_client.get("/user-id")
        assert resp.status_code == 401
