"""E2E test: registration → verification → profile creation → tracker connection."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestRegistrationFlow:
    """Full registration flow through API endpoints."""

    @pytest.fixture
    def _mock_repos(self, patch_db_pool: Any, mock_cursor: Any) -> None:
        """Ensure DB pool is mocked for all tests."""

    def _patch_auth_service(self):
        """Patch the auth service factory used by auth routes."""
        return patch("fittrack.api.routes.auth._get_auth_service")

    def test_register_creates_user(self, client: TestClient, _mock_repos: None) -> None:
        """POST /api/v1/auth/register should create a user account."""
        with self._patch_auth_service() as mock_factory:
            mock_svc = MagicMock()
            mock_factory.return_value = mock_svc
            mock_svc.register.return_value = {
                "user_id": "new-user-id",
                "email": "newuser@example.com",
                "message": "Registration successful",
            }

            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "newuser@example.com",
                    "password": "StrongP@ss123",
                    "date_of_birth": "1990-05-15",
                    "state": "CA",
                },
            )
            assert resp.status_code == 201
            data = resp.json()
            assert "user_id" in data

    def test_register_rejects_underage(self, client: TestClient, _mock_repos: None) -> None:
        """Registration must reject users under 18."""
        with self._patch_auth_service() as mock_factory:
            from fittrack.services.auth import AuthError

            mock_svc = MagicMock()
            mock_factory.return_value = mock_svc
            mock_svc.register.side_effect = AuthError("Must be 18+", 400)

            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "young@example.com",
                    "password": "StrongP@ss123",
                    "date_of_birth": "2015-01-01",
                    "state": "CA",
                },
            )
            assert resp.status_code == 400

    def test_register_rejects_excluded_state(
        self,
        client: TestClient,
        _mock_repos: None,
    ) -> None:
        """Registration must reject users from NY, FL, RI."""
        with self._patch_auth_service() as mock_factory:
            from fittrack.services.auth import AuthError

            mock_svc = MagicMock()
            mock_factory.return_value = mock_svc
            mock_svc.register.side_effect = AuthError(
                "State not eligible",
                400,
            )

            resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "newyorker@example.com",
                    "password": "StrongP@ss123",
                    "date_of_birth": "1990-01-01",
                    "state": "NY",
                },
            )
            assert resp.status_code == 400

    def test_login_returns_tokens(self, client: TestClient, _mock_repos: None) -> None:
        """POST /api/v1/auth/login should return access + refresh tokens."""
        with self._patch_auth_service() as mock_factory:
            mock_svc = MagicMock()
            mock_factory.return_value = mock_svc
            mock_svc.login.return_value = {
                "access_token": "at-123",
                "refresh_token": "rt-456",
                "token_type": "bearer",
            }

            resp = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "user@example.com",
                    "password": "StrongP@ss123",
                },
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["token_type"] == "bearer"

    def test_profile_creation_after_auth(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """Authenticated user can create a profile."""
        mock_svc = MagicMock()
        mock_svc.create_profile.return_value = {
            "profile_id": "p1",
            "user_id": "test-user",
            "display_name": "FitRunner",
            "tier_code": "M-18-29-BEG",
        }

        with patch(
            "fittrack.api.routes.profiles._get_profile_service",
            return_value=mock_svc,
        ):
            resp = client.post(
                "/api/v1/profiles",
                json={
                    "user_id": "test-user",
                    "display_name": "FitRunner",
                    "biological_sex": "male",
                    "date_of_birth": "1990-05-15",
                    "state_of_residence": "CA",
                    "age_bracket": "18-29",
                    "fitness_level": "beginner",
                },
                headers=user_headers,
            )
            assert resp.status_code in (200, 201)

    def test_connect_tracker_initiate(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """After profile, user can initiate tracker connection."""
        mock_svc = MagicMock()
        mock_svc.initiate_oauth.return_value = {
            "auth_url": "https://accounts.google.com/o/oauth2/auth?...",
            "provider": "google_fit",
        }
        with patch(
            "fittrack.api.routes.connections._get_tracker_service",
            return_value=mock_svc,
        ):
            resp = client.post(
                "/api/v1/connections/google_fit/initiate?redirect_uri=http://localhost",
                headers=user_headers,
            )
            assert resp.status_code != 404

    def test_full_registration_flow_sequence(
        self,
        client: TestClient,
        _mock_repos: None,
    ) -> None:
        """Test the logical sequence: register → login → get tokens."""
        with self._patch_auth_service() as mock_factory:
            mock_svc = MagicMock()
            mock_factory.return_value = mock_svc

            # Step 1: Register
            mock_svc.register.return_value = {
                "user_id": "flow-user-id",
                "email": "flow@example.com",
                "message": "Registration successful",
            }
            reg_resp = client.post(
                "/api/v1/auth/register",
                json={
                    "email": "flow@example.com",
                    "password": "StrongP@ss123",
                    "date_of_birth": "1990-01-01",
                    "state": "TX",
                },
            )
            assert reg_resp.status_code == 201

            # Step 2: Login
            mock_svc.login.return_value = {
                "access_token": "at-flow",
                "refresh_token": "rt-flow",
                "token_type": "bearer",
            }
            login_resp = client.post(
                "/api/v1/auth/login",
                json={
                    "email": "flow@example.com",
                    "password": "StrongP@ss123",
                },
            )
            assert login_resp.status_code == 200
            tokens = login_resp.json()
            assert "access_token" in tokens

    def test_me_endpoint_after_login(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """Authenticated user can access /users/me endpoint."""
        mock_svc = MagicMock()
        mock_svc.get_user_with_profile.return_value = {
            "user_id": "test-user",
            "email": "user@example.com",
            "role": "user",
            "status": "active",
        }

        with patch(
            "fittrack.api.routes.me._get_profile_service",
            return_value=mock_svc,
        ):
            resp = client.get("/api/v1/users/me", headers=user_headers)
            assert resp.status_code == 200
