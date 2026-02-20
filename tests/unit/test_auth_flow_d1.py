"""Checkpoint D1 — register → login → protected endpoint (integration-style).

Tests exercise the real AuthService business logic (password hashing, JWT
creation, lockout, etc.) through the FastAPI routes.  Only the DB layer
(repositories) is replaced by lightweight in-memory fakes so the tests run
without Oracle.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# ── In-memory fake repos ────────────────────────────────────────────


class FakeUserRepo:
    """Dictionary-backed user repository."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, *, data: dict[str, Any], new_id: str) -> str:
        row = {**data, "user_id": new_id}
        self._store[new_id] = row
        return new_id

    def find_by_id(self, uid: str) -> dict[str, Any] | None:
        row = self._store.get(uid)
        return dict(row) if row else None

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [dict(r) for r in self._store.values() if r.get(field) == value]

    def update(self, uid: str, data: dict[str, Any]) -> int:
        if uid not in self._store:
            return 0
        self._store[uid].update(data)
        return 1


class FakeSessionRepo:
    """Dictionary-backed session repository."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, *, data: dict[str, Any], new_id: str) -> str:
        row = {**data, "session_id": new_id, "revoked": 0}
        self._store[new_id] = row
        return new_id

    def find_by_id(self, sid: str) -> dict[str, Any] | None:
        return self._store.get(sid)

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [r for r in self._store.values() if r.get(field) == value]

    def update(self, sid: str, data: dict[str, Any]) -> int:
        if sid not in self._store:
            return 0
        self._store[sid].update(data)
        return 1


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture()
def _shared_repos():
    """Fake repos shared across register, login, and /me calls."""
    user_repo = FakeUserRepo()
    session_repo = FakeSessionRepo()
    return user_repo, session_repo


@pytest.fixture()
def d1_client(_shared_repos, patch_db_pool) -> TestClient:
    """TestClient wired to real AuthService with in-memory repos."""
    user_repo, session_repo = _shared_repos

    from fittrack.core.config import Settings
    from fittrack.main import create_app
    from fittrack.services.auth import AuthService

    svc = AuthService(user_repo=user_repo, session_repo=session_repo)

    app = create_app(settings=Settings(app_env="testing"))
    with patch("fittrack.api.routes.auth._get_auth_service", return_value=svc):
        yield TestClient(app)


# ── D1 integration tests ───────────────────────────────────────────


_REG_PAYLOAD = {
    "email": "alice@fittrack.dev",
    "password": "SecureP@ss1!",
    "date_of_birth": "1995-06-15",
    "state": "CA",
}


class TestD1RegisterLoginMe:
    """Full register → login → /me flow."""

    def test_register_returns_tokens(self, d1_client: TestClient) -> None:
        resp = d1_client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == _REG_PAYLOAD["email"]

    def test_login_after_register(self, d1_client: TestClient) -> None:
        # Register first
        self._register(d1_client)
        # Login
        resp = d1_client.post(
            "/api/v1/auth/login",
            json={
                "email": _REG_PAYLOAD["email"],
                "password": _REG_PAYLOAD["password"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["role"] == "user"

    def test_me_with_token_from_login(self, d1_client: TestClient) -> None:
        """register → login → GET /me with Bearer token."""
        self._register(d1_client)
        login_resp = d1_client.post(
            "/api/v1/auth/login",
            json={
                "email": _REG_PAYLOAD["email"],
                "password": _REG_PAYLOAD["password"],
            },
        )
        token = login_resp.json()["access_token"]

        me_resp = d1_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200
        me = me_resp.json()
        assert me["email"] == _REG_PAYLOAD["email"]
        # Sensitive fields must be stripped
        assert "password_hash" not in me

    def test_me_with_token_from_register(self, d1_client: TestClient) -> None:
        """The access_token returned at registration is immediately usable."""
        reg_resp = d1_client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        token = reg_resp.json()["access_token"]

        me_resp = d1_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert me_resp.status_code == 200

    def test_duplicate_email_rejected(self, d1_client: TestClient) -> None:
        self._register(d1_client)
        resp = d1_client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 409

    def test_wrong_password_rejected(self, d1_client: TestClient) -> None:
        self._register(d1_client)
        resp = d1_client.post(
            "/api/v1/auth/login",
            json={
                "email": _REG_PAYLOAD["email"],
                "password": "WrongPassword123!",
            },
        )
        assert resp.status_code == 401

    # helper
    @staticmethod
    def _register(client: TestClient) -> dict[str, Any]:
        resp = client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 201
        return resp.json()


class TestD1ProtectedWithoutToken:
    """Protected endpoints must reject unauthenticated requests."""

    def test_me_no_token_returns_401(self, d1_client: TestClient) -> None:
        resp = d1_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token_returns_401(self, d1_client: TestClient) -> None:
        resp = d1_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer garbage.token.here"},
        )
        assert resp.status_code == 401

    def test_logout_no_token_returns_401(self, d1_client: TestClient) -> None:
        resp = d1_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    def test_logout_all_no_token_returns_401(self, d1_client: TestClient) -> None:
        resp = d1_client.post("/api/v1/auth/logout-all")
        assert resp.status_code == 401


class TestD1EdgeCases:
    """Additional validation edge cases for local auth."""

    def test_excluded_state_ny(self, d1_client: TestClient) -> None:
        payload = {**_REG_PAYLOAD, "email": "ny@test.com", "state": "NY"}
        resp = d1_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 403)

    def test_excluded_state_fl(self, d1_client: TestClient) -> None:
        payload = {**_REG_PAYLOAD, "email": "fl@test.com", "state": "FL"}
        resp = d1_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code in (400, 403)

    def test_underage_rejected(self, d1_client: TestClient) -> None:
        payload = {**_REG_PAYLOAD, "email": "kid@test.com", "date_of_birth": "2015-01-01"}
        resp = d1_client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 403

    def test_refresh_token_works(self, d1_client: TestClient) -> None:
        reg = self._register(d1_client)
        resp = d1_client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": reg["refresh_token"],
            },
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    @staticmethod
    def _register(client: TestClient) -> dict[str, Any]:
        resp = client.post("/api/v1/auth/register", json=_REG_PAYLOAD)
        assert resp.status_code == 201
        return resp.json()
