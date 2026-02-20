"""Tests for points routes — /api/v1/points."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import MockCursor, set_mock_query_result


class TestPointsBalance:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/points/balance")
        assert resp.status_code == 401

    def test_get_balance(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # get_current_user query, then get_balance, then get_points_earned
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 500)],
        )
        resp = client.get("/api/v1/points/balance", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "user_id" in data
        assert "point_balance" in data
        assert "points_earned" in data


class TestPointsTransactions:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/points/transactions")
        assert resp.status_code == 401

    def test_get_transactions(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        resp = client.get("/api/v1/points/transactions", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_pagination(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        resp = client.get("/api/v1/points/transactions?page=3&limit=5", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["page"] == 3
        assert data["pagination"]["limit"] == 5


class TestPointsDaily:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/points/daily")
        assert resp.status_code == 401

    def test_daily_status(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        resp = client.get("/api/v1/points/daily", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "daily_cap" in data
        assert "remaining" in data
        assert "points_earned_today" in data
        assert data["daily_cap"] == 1000


class TestPointsStreak:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/points/streak")
        assert resp.status_code == 401

    def test_streak(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        resp = client.get("/api/v1/points/streak", headers=user_headers)
        assert resp.status_code == 200
