"""Tests for connection routes — /api/v1/connections."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import MockCursor, set_mock_query_result


class TestListConnections:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/connections")
        assert resp.status_code == 401

    def test_list_connections(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # JWT lookup then connection_repo.find_by_user_id
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        resp = client.get("/api/v1/connections", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "count" in data


class TestInitiateOAuth:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/connections/google_fit/initiate?redirect_uri=http://cb"
        )
        assert resp.status_code == 401

    def test_unsupported_provider(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.post(
            "/api/v1/connections/unknown_provider/initiate?redirect_uri=http://cb",
            headers=user_headers,
        )
        assert resp.status_code == 400

    def test_initiate_google_fit(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # find_by_user_id returns empty (no existing connections)
        set_mock_query_result(mock_cursor, ["connection_id"], [])
        resp = client.post(
            "/api/v1/connections/google_fit/initiate?redirect_uri=http://localhost/cb",
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data
        assert "state" in data


class TestCompleteOAuth:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/connections/google_fit/callback"
            "?code=auth_code&redirect_uri=http://cb"
        )
        assert resp.status_code == 401

    def test_unsupported_provider(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.post(
            "/api/v1/connections/unknown/callback"
            "?code=auth_code&redirect_uri=http://cb",
            headers=user_headers,
        )
        assert resp.status_code == 400

    def test_complete_google_fit(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # find_by_user_id returns empty (first connection)
        set_mock_query_result(mock_cursor, ["connection_id"], [])
        resp = client.post(
            "/api/v1/connections/google_fit/callback"
            "?code=test_code&redirect_uri=http://localhost/cb",
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["provider"] == "google_fit"
        assert "connection_id" in data


class TestDisconnect:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/connections/google_fit")
        assert resp.status_code == 401

    def test_unsupported_provider(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.delete(
            "/api/v1/connections/unknown", headers=user_headers
        )
        assert resp.status_code == 400


class TestForceSync:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/v1/connections/google_fit/sync")
        assert resp.status_code == 401

    def test_unsupported_provider(
        self, client: TestClient, mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.post(
            "/api/v1/connections/unknown/sync", headers=user_headers
        )
        assert resp.status_code == 400
