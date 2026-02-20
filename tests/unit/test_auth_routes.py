"""Tests for auth API routes — /api/v1/auth/*."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _patch_auth_repos():
    """Patch both user and session repos used by auth routes."""
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_field = MagicMock(return_value=[])
    mock_user_repo.find_by_id = MagicMock(return_value=None)
    mock_user_repo.create = MagicMock()
    mock_user_repo.update = MagicMock(return_value=1)

    mock_session_repo = MagicMock()
    mock_session_repo.create = MagicMock()
    mock_session_repo.find_by_id = MagicMock(return_value={"session_id": "s1", "revoked": 0})
    mock_session_repo.find_by_field = MagicMock(return_value=[])
    mock_session_repo.update = MagicMock(return_value=1)

    with (
        patch(
            "fittrack.api.routes.auth._get_auth_service",
        ) as mock_svc_factory,
    ):
        from fittrack.services.auth import AuthService

        svc = AuthService(user_repo=mock_user_repo, session_repo=mock_session_repo)
        mock_svc_factory.return_value = svc
        yield svc, mock_user_repo, mock_session_repo


@pytest.fixture
def auth_client(patch_db_pool, _patch_auth_repos) -> TestClient:
    """Client with auth repos patched."""
    from fittrack.core.config import Settings
    from fittrack.main import create_app

    app = create_app(settings=Settings(app_env="testing"))
    return TestClient(app)


class TestRegisterRoute:
    """POST /api/v1/auth/register."""

    def test_register_success(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "Str0ng!Pass",
                "date_of_birth": "1990-01-15",
                "state": "TX",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_register_weak_password(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@example.com",
                "password": "weak",
                "date_of_birth": "1990-01-15",
                "state": "TX",
            },
        )
        # Pydantic validation: min_length=8
        assert resp.status_code == 422

    def test_register_invalid_email(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "password": "Str0ng!Pass",
                "date_of_birth": "1990-01-15",
                "state": "TX",
            },
        )
        assert resp.status_code == 422

    def test_register_bad_dob_format(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "x@y.com",
                "password": "Str0ng!Pass",
                "date_of_birth": "01/15/1990",
                "state": "TX",
            },
        )
        assert resp.status_code == 422

    def test_register_bad_state(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/register",
            json={
                "email": "x@y.com",
                "password": "Str0ng!Pass",
                "date_of_birth": "1990-01-15",
                "state": "NY",
            },
        )
        assert resp.status_code == 403


class TestLoginRoute:
    """POST /api/v1/auth/login."""

    def test_login_no_user(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "nobody@example.com",
                "password": "Str0ng!Pass",
            },
        )
        assert resp.status_code == 401

    def test_login_missing_fields(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/login",
            json={
                "email": "a@b.com",
            },
        )
        assert resp.status_code == 422


class TestSocialRoutes:
    """Social login stubs."""

    def test_google_returns_501(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/social/google")
        assert resp.status_code == 501

    def test_apple_returns_501(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/social/apple")
        assert resp.status_code == 501


class TestProtectedRoutes:
    """Routes requiring authentication."""

    def test_me_without_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_invalid_token(self, auth_client: TestClient) -> None:
        resp = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token"},
        )
        assert resp.status_code == 401

    def test_me_with_valid_token(self, auth_client: TestClient, _patch_auth_repos) -> None:
        from fittrack.core.security import create_access_token

        svc, user_repo, _ = _patch_auth_repos
        user_repo.find_by_id = MagicMock(
            return_value={
                "user_id": "uid1",
                "email": "test@example.com",
                "status": "active",
                "role": "user",
                "password_hash": "HIDDEN",
            }
        )

        token = create_access_token(subject="uid1", role="user")
        resp = auth_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"
        # Password hash should be stripped
        assert "password_hash" not in data

    def test_logout_without_token(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/logout")
        assert resp.status_code == 401

    def test_logout_all_without_token(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/logout-all")
        assert resp.status_code == 401


class TestRefreshRoute:
    """POST /api/v1/auth/refresh."""

    def test_refresh_missing_token(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/refresh", json={})
        assert resp.status_code == 422

    def test_refresh_invalid_token(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/refresh",
            json={
                "refresh_token": "invalid.token.here",
            },
        )
        assert resp.status_code == 401


class TestForgotPasswordRoute:
    """POST /api/v1/auth/forgot-password."""

    def test_forgot_password(self, auth_client: TestClient) -> None:
        resp = auth_client.post(
            "/api/v1/auth/forgot-password",
            json={
                "email": "test@example.com",
            },
        )
        assert resp.status_code == 200
        assert "reset_token" in resp.json()


class TestVerifyEmailRoute:
    """POST /api/v1/auth/verify-email."""

    def test_verify_missing_fields(self, auth_client: TestClient) -> None:
        resp = auth_client.post("/api/v1/auth/verify-email", json={})
        assert resp.status_code == 422
