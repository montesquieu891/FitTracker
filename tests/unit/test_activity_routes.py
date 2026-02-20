"""Tests for activity routes — /api/v1/activities."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.conftest import MockCursor, set_mock_query_result


class TestListActivities:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/activities")
        assert resp.status_code == 401

    def test_lists_activities(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # First call is count, second is find_all
        set_mock_query_result(
            mock_cursor,
            ["cnt"],
            [(2,)],
        )
        resp = client.get("/api/v1/activities", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_pagination_params(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/activities?page=2&limit=10", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["page"] == 2
        assert data["pagination"]["limit"] == 10


class TestActivitySummary:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/activities/summary")
        assert resp.status_code == 401

    def test_summary_today(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # find_by_user_and_date_range returns no activities
        set_mock_query_result(mock_cursor, ["activity_id"], [])
        resp = client.get("/api/v1/activities/summary?period=today", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "today"
        assert data["total_steps"] == 0
        assert data["workout_count"] == 0

    def test_summary_week(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["activity_id"], [])
        resp = client.get("/api/v1/activities/summary?period=week", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["period"] == "week"

    def test_summary_month(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        set_mock_query_result(mock_cursor, ["activity_id"], [])
        resp = client.get("/api/v1/activities/summary?period=month", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["period"] == "month"

    def test_invalid_period(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.get("/api/v1/activities/summary?period=year", headers=user_headers)
        assert resp.status_code == 422


class TestCreateActivity:
    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/v1/activities", json={})
        assert resp.status_code == 401

    def test_create_activity(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        # get_current_user -> user query
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "role", "status", "point_balance"],
            [("test-user", "user@example.com", "user", "active", 0)],
        )
        body = {
            "user_id": "test-user",
            "activity_type": "steps",
            "start_time": "2026-01-15T08:00:00Z",
            "metrics": {"step_count": 8000},
        }
        resp = client.post("/api/v1/activities", json=body, headers=user_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert "activity_id" in data
        assert data["activity_type"] == "steps"

    def test_invalid_activity_type(
        self,
        client: TestClient,
        mock_cursor: MockCursor,
        user_headers: dict[str, str],
    ) -> None:
        body = {
            "user_id": "test-user",
            "activity_type": "swimming",
            "start_time": "2026-01-15T08:00:00Z",
        }
        resp = client.post("/api/v1/activities", json=body, headers=user_headers)
        assert resp.status_code == 422

    def test_create_workout(
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
        body = {
            "user_id": "test-user",
            "activity_type": "workout",
            "start_time": "2026-01-15T08:00:00Z",
            "end_time": "2026-01-15T09:00:00Z",
            "duration_minutes": 60,
            "intensity": "moderate",
            "metrics": {"calories_burned": 500},
        }
        resp = client.post("/api/v1/activities", json=body, headers=user_headers)
        assert resp.status_code == 201

    def test_create_active_minutes(
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
        body = {
            "user_id": "test-user",
            "activity_type": "active_minutes",
            "start_time": "2026-01-15T08:00:00Z",
            "duration_minutes": 30,
            "intensity": "vigorous",
        }
        resp = client.post("/api/v1/activities", json=body, headers=user_headers)
        assert resp.status_code == 201
