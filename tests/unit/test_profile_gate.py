"""Tests for the profile gate middleware."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fittrack.api.profile_gate import (
    _is_allowed_path,
    _is_get_request,
    _is_profile_path,
    profile_gate_middleware,
)
from fittrack.core.security import create_access_token

# ── Helper-function unit tests ──────────────────────────────────────


class TestIsAllowedPath:
    """Test _is_allowed_path path matching."""

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/docs",
            "/openapi.json",
            "/redoc",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/dev/migrate",
            "/api/v1/tiers",
            "/api/v1/tiers/M-18-29-BEG",
            "/static/test_page.html",
            "/test",
        ],
    )
    def test_allowed_paths(self, path: str) -> None:
        assert _is_allowed_path(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/activities",
            "/api/v1/drawings",
            "/api/v1/tickets",
            "/api/v1/users",
            "/api/v1/sponsors",
        ],
    )
    def test_blocked_paths(self, path: str) -> None:
        assert _is_allowed_path(path) is False


class TestIsProfilePath:
    """Test _is_profile_path matching."""

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/profiles",
            "/api/v1/profiles/p1",
            "/api/v1/users/me",
            "/api/v1/users/me/profile",
            "/api/v1/users/me/profile/complete",
        ],
    )
    def test_profile_paths(self, path: str) -> None:
        assert _is_profile_path(path) is True

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/users/u1",
            "/api/v1/activities",
            "/api/v1/drawings",
        ],
    )
    def test_non_profile_paths(self, path: str) -> None:
        assert _is_profile_path(path) is False


class TestIsGetRequest:
    """Test _is_get_request."""

    def test_get(self) -> None:
        assert _is_get_request("GET") is True

    def test_get_lowercase(self) -> None:
        assert _is_get_request("get") is True

    def test_post(self) -> None:
        assert _is_get_request("POST") is False

    def test_put(self) -> None:
        assert _is_get_request("PUT") is False

    def test_delete(self) -> None:
        assert _is_get_request("DELETE") is False


# ── Integration tests with a real FastAPI app ───────────────────────


def _make_gated_app() -> FastAPI:
    """Build a minimal FastAPI app with profile gate middleware."""
    from fastapi import Request

    app = FastAPI()

    @app.middleware("http")
    async def gate(request: Request, call_next: Any) -> Any:
        return await profile_gate_middleware(request, call_next)

    @app.get("/api/v1/tiers")
    def list_tiers() -> dict[str, str]:
        return {"ok": "tiers"}

    @app.get("/api/v1/activities")
    def list_activities() -> dict[str, str]:
        return {"ok": "activities"}

    @app.post("/api/v1/activities")
    def create_activity() -> dict[str, str]:
        return {"ok": "created"}

    @app.post("/api/v1/tickets")
    def buy_ticket() -> dict[str, str]:
        return {"ok": "ticket"}

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"ok": "health"}

    @app.put("/api/v1/users/me/profile")
    def upsert_profile() -> dict[str, str]:
        return {"ok": "profile"}

    @app.post("/api/v1/auth/login")
    def login() -> dict[str, str]:
        return {"ok": "login"}

    return app


class TestProfileGateMiddleware:
    """Integration tests for profile_gate_middleware."""

    @pytest.fixture
    def gated_client(self) -> TestClient:
        return TestClient(_make_gated_app())

    def _auth_header(self, role: str = "user") -> dict[str, str]:
        token = create_access_token(subject="test-user", role=role)
        return {"Authorization": f"Bearer {token}"}

    # ── Allowed paths always pass through ────────────────────────

    def test_health_always_allowed(self, gated_client: TestClient) -> None:
        resp = gated_client.get("/health")
        assert resp.status_code == 200

    def test_tiers_always_allowed(self, gated_client: TestClient) -> None:
        resp = gated_client.get("/api/v1/tiers")
        assert resp.status_code == 200

    def test_auth_always_allowed(self, gated_client: TestClient) -> None:
        resp = gated_client.post("/api/v1/auth/login")
        assert resp.status_code == 200

    def test_profile_path_always_allowed(
        self,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.put(
            "/api/v1/users/me/profile",
            headers=self._auth_header(),
        )
        assert resp.status_code == 200

    # ── GET requests pass through ────────────────────────────────

    def test_get_activities_allowed_without_profile(
        self,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.get(
            "/api/v1/activities",
            headers=self._auth_header(),
        )
        assert resp.status_code == 200

    # ── Unauthenticated passes through (route handles auth) ─────

    def test_unauthenticated_post_passes_through(
        self,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.post("/api/v1/activities")
        assert resp.status_code == 200

    # ── Admin bypasses gate ──────────────────────────────────────

    @patch("fittrack.core.database.get_pool", return_value=None)
    def test_admin_bypasses_gate(
        self,
        _pool: Any,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.post(
            "/api/v1/activities",
            headers=self._auth_header(role="admin"),
        )
        assert resp.status_code == 200

    # ── Incomplete profile blocks write requests ─────────────────

    def test_no_profile_blocks_post(
        self,
        gated_client: TestClient,
    ) -> None:
        """POST to a feature endpoint is blocked for user with no profile."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []  # no profile found
        mock_cursor.description = None
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_pool.acquire.return_value = mock_conn

        with patch(
            "fittrack.core.database.get_pool",
            return_value=mock_pool,
        ):
            resp = gated_client.post(
                "/api/v1/activities",
                headers=self._auth_header(),
            )
        assert resp.status_code == 403
        data = resp.json()
        assert data["title"] == "Profile Incomplete"
        assert "action" in data

    def test_incomplete_profile_blocks_post(
        self,
        gated_client: TestClient,
    ) -> None:
        """POST blocked when profile exists but is missing required fields."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # Return a row with columns but display_name is None
        mock_cursor.description = [
            ("PROFILE_ID",),
            ("USER_ID",),
            ("DISPLAY_NAME",),
            ("DATE_OF_BIRTH",),
            ("STATE_OF_RESIDENCE",),
            ("BIOLOGICAL_SEX",),
            ("AGE_BRACKET",),
            ("FITNESS_LEVEL",),
        ]
        mock_cursor.fetchall.return_value = [
            (
                "p1",
                "test-user",
                None,  # display_name is None
                "1990-01-01",
                "CA",
                "male",
                "18-29",
                "beginner",
            ),
        ]
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_pool.acquire.return_value = mock_conn

        with patch(
            "fittrack.core.database.get_pool",
            return_value=mock_pool,
        ):
            resp = gated_client.post(
                "/api/v1/activities",
                headers=self._auth_header(),
            )
        assert resp.status_code == 403

    def test_complete_profile_allows_post(
        self,
        gated_client: TestClient,
    ) -> None:
        """POST allowed when user has a complete profile."""
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.description = [
            ("PROFILE_ID",),
            ("USER_ID",),
            ("DISPLAY_NAME",),
            ("DATE_OF_BIRTH",),
            ("STATE_OF_RESIDENCE",),
            ("BIOLOGICAL_SEX",),
            ("AGE_BRACKET",),
            ("FITNESS_LEVEL",),
        ]
        mock_cursor.fetchall.return_value = [
            ("p1", "test-user", "Jane Doe", "1990-01-01", "CA", "female", "30-39", "intermediate"),
        ]
        mock_cursor.__enter__ = lambda s: s
        mock_cursor.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cursor
        mock_conn.__enter__ = lambda s: s
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_pool.acquire.return_value = mock_conn

        with patch(
            "fittrack.core.database.get_pool",
            return_value=mock_pool,
        ):
            resp = gated_client.post(
                "/api/v1/activities",
                headers=self._auth_header(),
            )
        assert resp.status_code == 200

    # ── No DB pool → allow through (dev/test mode) ──────────────

    @patch("fittrack.core.database.get_pool", return_value=None)
    def test_no_pool_allows_through(
        self,
        _pool: Any,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.post(
            "/api/v1/activities",
            headers=self._auth_header(),
        )
        assert resp.status_code == 200

    # ── DB error → allow through gracefully ─────────────────────

    def test_db_error_allows_through(
        self,
        gated_client: TestClient,
    ) -> None:
        with patch(
            "fittrack.core.database.get_pool",
            side_effect=Exception("DB down"),
        ):
            resp = gated_client.post(
                "/api/v1/activities",
                headers=self._auth_header(),
            )
        assert resp.status_code == 200

    # ── Invalid/expired token passes through ────────────────────

    def test_invalid_token_passes_through(
        self,
        gated_client: TestClient,
    ) -> None:
        resp = gated_client.post(
            "/api/v1/activities",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 200
