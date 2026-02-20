"""Tests for CP3 profile routes and /users/me endpoints."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import MockCursor, set_mock_query_result

# ── /api/v1/users/me ────────────────────────────────────────────────


class TestMeRoutes:
    """Test /api/v1/users/me endpoint."""

    def test_get_me_returns_user_with_profile(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/users/me returns merged user + profile."""
        # First call: user_repo.find_by_id
        # Second call: profile_repo.find_by_user_id
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 100)],
        )
        resp = client.get("/api/v1/users/me", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "test-user"
        assert "profile_complete" in data

    def test_get_me_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me")
        assert resp.status_code == 401

    def test_get_me_profile_returns_profile(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/users/me/profile returns user's profile."""
        set_mock_query_result(
            mock_cursor,
            [
                "profile_id",
                "user_id",
                "display_name",
                "tier_code",
                "biological_sex",
                "age_bracket",
                "fitness_level",
            ],
            [
                (
                    "p1",
                    "test-user",
                    "Test User",
                    "M-18-29-BEG",
                    "male",
                    "18-29",
                    "beginner",
                )
            ],
        )
        resp = client.get("/api/v1/users/me/profile", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["profile_id"] == "p1"

    def test_get_me_profile_404_when_none(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        resp = client.get("/api/v1/users/me/profile", headers=user_headers)
        assert resp.status_code == 404

    def test_get_me_profile_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/profile")
        assert resp.status_code == 401


class TestMeProfileUpsert:
    """Test PUT /api/v1/users/me/profile (create or update)."""

    def _profile_body(self) -> dict[str, Any]:
        return {
            "user_id": "ignored",
            "display_name": "Jane Doe",
            "date_of_birth": "1990-05-15",
            "state_of_residence": "CA",
            "biological_sex": "female",
            "age_bracket": "30-39",
            "fitness_level": "intermediate",
        }

    def test_upsert_creates_when_no_existing(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        """PUT creates a new profile when none exists."""
        # find_by_user_id (for service.get_profile_by_user_id) → None
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        mock_cursor.rowcount = 1
        resp = client.put(
            "/api/v1/users/me/profile",
            json=self._profile_body(),
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "profile_id" in data
        assert data["tier_code"] == "F-30-39-INT"

    def test_upsert_requires_auth(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/users/me/profile",
            json=self._profile_body(),
        )
        assert resp.status_code == 401

    def test_upsert_invalid_sex_422(
        self,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        body = self._profile_body()
        body["biological_sex"] = "other"
        resp = client.put(
            "/api/v1/users/me/profile",
            json=body,
            headers=user_headers,
        )
        assert resp.status_code == 422


class TestMeProfilePatch:
    """Test PATCH /api/v1/users/me/profile (partial update)."""

    def test_patch_requires_auth(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/users/me/profile",
            json={"display_name": "Updated"},
        )
        assert resp.status_code == 401

    def test_patch_404_when_no_profile(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        resp = client.patch(
            "/api/v1/users/me/profile",
            json={"display_name": "Updated"},
            headers=user_headers,
        )
        assert resp.status_code == 404

    def test_patch_empty_body_400(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # find_by_user_id returns a profile
        set_mock_query_result(
            mock_cursor,
            ["profile_id", "user_id", "display_name"],
            [("p1", "test-user", "Test User")],
        )
        resp = client.patch(
            "/api/v1/users/me/profile",
            json={},
            headers=user_headers,
        )
        assert resp.status_code == 400


class TestMeProfileComplete:
    """Test GET /api/v1/users/me/profile/complete."""

    def test_complete_check_no_profile(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        resp = client.get(
            "/api/v1/users/me/profile/complete",
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["profile_complete"] is False

    def test_complete_check_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/users/me/profile/complete")
        assert resp.status_code == 401


# ── /api/v1/users/{id}/public ───────────────────────────────────────


class TestPublicProfile:
    """Test GET /api/v1/users/{id}/public."""

    def test_public_profile_200(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
    ) -> None:
        set_mock_query_result(
            mock_cursor,
            [
                "profile_id",
                "user_id",
                "display_name",
                "tier_code",
                "biological_sex",
                "age_bracket",
                "fitness_level",
            ],
            [
                (
                    "p1",
                    "u1",
                    "Jane Doe",
                    "F-30-39-INT",
                    "female",
                    "30-39",
                    "intermediate",
                )
            ],
        )
        resp = client.get("/api/v1/users/u1/public")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "u1"
        assert data["display_name"] == "Jane Doe"
        assert data["tier_code"] == "F-30-39-INT"
        # Should not expose sensitive fields
        assert "email" not in data
        assert "password_hash" not in data

    def test_public_profile_404(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
    ) -> None:
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        resp = client.get("/api/v1/users/nonexistent/public")
        assert resp.status_code == 404
