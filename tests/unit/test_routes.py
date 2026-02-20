"""TDD RED: Tests for API routes — written BEFORE route implementations."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from tests.conftest import MockCursor, set_mock_query_result


class TestHealthRoute:
    """Test health check endpoint."""

    def test_health_returns_200(self, client: TestClient) -> None:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"

    def test_health_response_structure(self, client: TestClient) -> None:
        resp = client.get("/health")
        data = resp.json()
        assert "status" in data
        assert "environment" in data


class TestUserRoutes:
    """Test /api/v1/users endpoints."""

    def test_list_users_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/users")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_create_user_201(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/users",
            json={"email": "new@example.com", "password_hash": "hashed123"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "user_id" in data

    def test_create_user_invalid_email_422(self, client: TestClient, admin_headers: dict) -> None:
        resp = client.post(
            "/api/v1/users",
            json={"email": "not-valid", "password_hash": "hash"},
            headers=admin_headers,
        )
        assert resp.status_code == 422

    def test_get_user_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(
            mock_cursor,
            ["user_id", "email", "status", "role", "point_balance"],
            [("u1", "test@example.com", "active", "user", 0)],
        )
        resp = client.get("/api/v1/users/u1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == "u1"

    def test_get_user_404(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["user_id"], [])
        resp = client.get("/api/v1/users/nonexistent")
        assert resp.status_code == 404

    def test_update_user_200(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.patch(
            "/api/v1/users/u1", json={"status": "active"}, headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_delete_user_204(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.delete("/api/v1/users/u1", headers=admin_headers)
        assert resp.status_code == 204


class TestSponsorRoutes:
    """Test /api/v1/sponsors endpoints."""

    def test_list_sponsors_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/sponsors")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_create_sponsor_201(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/sponsors",
            json={"name": "TestSponsor"},
            headers=admin_headers,
        )
        assert resp.status_code == 201

    def test_get_sponsor_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(
            mock_cursor,
            ["sponsor_id", "name", "status"],
            [("s1", "TestSponsor", "active")],
        )
        resp = client.get("/api/v1/sponsors/s1")
        assert resp.status_code == 200

    def test_get_sponsor_404(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["sponsor_id"], [])
        resp = client.get("/api/v1/sponsors/nonexistent")
        assert resp.status_code == 404


class TestDrawingRoutes:
    """Test /api/v1/drawings endpoints."""

    def test_list_drawings_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/drawings")
        assert resp.status_code == 200

    def test_create_drawing_201(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/drawings",
            json={
                "drawing_type": "daily",
                "name": "Daily Draw",
                "ticket_cost_points": 100,
                "drawing_time": "2026-01-15T21:00:00",
                "ticket_sales_close": "2026-01-15T20:55:00",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_drawing_200(
        self, mock_factory: MagicMock, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_drawing.return_value = {
            "drawing_id": "d1", "drawing_type": "daily",
            "name": "Daily Draw", "ticket_cost_points": 100,
            "status": "open", "prizes": [], "total_tickets": 0,
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/d1")
        assert resp.status_code == 200

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_drawing_404(
        self, mock_factory: MagicMock, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        from fittrack.services.drawings import DrawingError
        mock_svc = MagicMock()
        mock_svc.get_drawing.side_effect = DrawingError("not found", 404)
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/nonexistent")
        assert resp.status_code == 404


class TestProfileRoutes:
    """Test /api/v1/profiles endpoints."""

    def test_list_profiles_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/profiles")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_create_profile_201(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/profiles",
            json={
                "user_id": "u1",
                "display_name": "Jane Doe",
                "date_of_birth": "1990-05-15",
                "state_of_residence": "CA",
                "biological_sex": "female",
                "age_bracket": "30-39",
                "fitness_level": "intermediate",
            },
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "profile_id" in data
        assert data["tier_code"] == "F-30-39-INT"

    def test_create_profile_invalid_sex_422(self, client: TestClient, user_headers: dict) -> None:
        resp = client.post(
            "/api/v1/profiles",
            json={
                "user_id": "u1",
                "display_name": "Jane",
                "date_of_birth": "1990-05-15",
                "state_of_residence": "CA",
                "biological_sex": "other",
                "age_bracket": "30-39",
                "fitness_level": "intermediate",
            },
            headers=user_headers,
        )
        assert resp.status_code == 422

    def test_get_profile_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(
            mock_cursor,
            ["profile_id", "user_id", "display_name", "tier_code"],
            [("p1", "u1", "Jane Doe", "F-30-39-INT")],
        )
        resp = client.get("/api/v1/profiles/p1")
        assert resp.status_code == 200
        assert resp.json()["profile_id"] == "p1"

    def test_get_profile_404(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["profile_id"], [])
        resp = client.get("/api/v1/profiles/nonexistent")
        assert resp.status_code == 404

    def test_update_profile_200(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        # Ownership check: find_by_id must return a profile owned by test-user
        set_mock_query_result(
            mock_cursor,
            ["profile_id", "user_id", "display_name"],
            [("p1", "test-user", "Old Name")],
        )
        mock_cursor.rowcount = 1
        resp = client.put(
            "/api/v1/profiles/p1",
            json={"display_name": "Updated Name"},
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["updated"] is True


class TestConnectionRoutes:
    """Test /api/v1/connections endpoints (CP4: OAuth flow routes)."""

    def test_list_connections_200(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        set_mock_query_result(mock_cursor, ["connection_id"], [])
        resp = client.get("/api/v1/connections", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_connections_requires_auth(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        resp = client.get("/api/v1/connections")
        assert resp.status_code == 401

    def test_initiate_oauth_200(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        set_mock_query_result(mock_cursor, ["connection_id"], [])
        resp = client.post(
            "/api/v1/connections/google_fit/initiate?redirect_uri=http://localhost/cb",
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "authorization_url" in data

    def test_unsupported_provider_400(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        resp = client.post(
            "/api/v1/connections/apple_health/initiate?redirect_uri=http://cb",
            headers=user_headers,
        )
        assert resp.status_code == 400

    def test_disconnect_requires_auth(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        resp = client.delete("/api/v1/connections/google_fit")
        assert resp.status_code == 401

    def test_disconnect_unsupported_provider_400(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        resp = client.delete(
            "/api/v1/connections/apple_health", headers=user_headers,
        )
        assert resp.status_code == 400


class TestActivityRoutes:
    """Test /api/v1/activities endpoints (CP4: auth-required)."""

    def test_list_activities_requires_auth(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        resp = client.get("/api/v1/activities")
        assert resp.status_code == 401

    def test_list_activities_200(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/activities", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_list_activities_with_filters(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get(
            "/api/v1/activities?activity_type=steps", headers=user_headers,
        )
        assert resp.status_code == 200

    def test_create_activity_201(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/activities",
            json={
                "user_id": "u1",
                "activity_type": "steps",
                "start_time": "2026-01-15T08:00:00",
            },
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "activity_id" in data

    def test_create_activity_invalid_type_422(self, client: TestClient, user_headers: dict) -> None:
        resp = client.post(
            "/api/v1/activities",
            json={
                "user_id": "u1",
                "activity_type": "swimming",
                "start_time": "2026-01-15T08:00:00",
            },
            headers=user_headers,
        )
        assert resp.status_code == 422


class TestTransactionRoutes:
    """Test /api/v1/transactions endpoints."""

    def test_list_transactions_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/transactions")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "pagination" in data

    def test_list_transactions_filter_by_user(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/transactions?user_id=u1")
        assert resp.status_code == 200

    def test_create_transaction_201(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/transactions",
            json={
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 100,
                "balance_after": 500,
            },
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "transaction_id" in data

    def test_create_transaction_invalid_type_422(
        self, client: TestClient, user_headers: dict,
    ) -> None:
        resp = client.post(
            "/api/v1/transactions",
            json={
                "user_id": "u1",
                "transaction_type": "refund",
                "amount": 100,
                "balance_after": 500,
            },
            headers=user_headers,
        )
        assert resp.status_code == 422


class TestTicketRoutes:
    """Test /api/v1/tickets endpoints."""

    def test_list_tickets_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/tickets")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_tickets_by_drawing(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/tickets?drawing_id=d1")
        assert resp.status_code == 200

    def test_create_ticket_201(
        self, client: TestClient, mock_cursor: MockCursor, user_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/tickets",
            json={"drawing_id": "d1", "user_id": "u1"},
            headers=user_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "ticket_id" in data


class TestPrizeRoutes:
    """Test /api/v1/prizes endpoints."""

    def test_list_prizes_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/prizes")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_list_prizes_by_drawing(self, client: TestClient, mock_cursor: MockCursor) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/prizes?drawing_id=d1")
        assert resp.status_code == 200

    def test_create_prize_201(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/prizes",
            json={
                "drawing_id": "d1",
                "rank": 1,
                "name": "Grand Prize",
                "value_usd": 500.0,
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "prize_id" in data

    def test_create_prize_invalid_rank_422(self, client: TestClient, admin_headers: dict) -> None:
        resp = client.post(
            "/api/v1/prizes",
            json={
                "drawing_id": "d1",
                "rank": 0,
                "name": "Bad Prize",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestFulfillmentRoutes:
    """Test /api/v1/fulfillments endpoints."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_list_fulfillments_200(
        self, mock_factory: MagicMock, client: TestClient,
        mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.list_fulfillments.return_value = {
            "items": [],
            "pagination": {"page": 1, "limit": 20, "total_items": 0, "total_pages": 1},
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/fulfillments", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_list_fulfillments_by_user(
        self, mock_factory: MagicMock, client: TestClient,
        mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.list_fulfillments.return_value = {
            "items": [],
            "pagination": {"page": 1, "limit": 20, "total_items": 0, "total_pages": 1},
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/fulfillments?user_id=u1", headers=admin_headers)
        assert resp.status_code == 200

    def test_create_fulfillment_201(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 1
        resp = client.post(
            "/api/v1/fulfillments",
            json={
                "ticket_id": "t1",
                "prize_id": "pr1",
                "user_id": "u1",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "fulfillment_id" in data

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_update_fulfillment_200(
        self, mock_factory: MagicMock, client: TestClient,
        mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.transition_status.return_value = {
            "fulfillment_id": "f1", "status": "winner_notified", "updated": True,
        }
        mock_factory.return_value = mock_svc
        resp = client.put(
            "/api/v1/fulfillments/f1",
            json={"status": "winner_notified"},
            headers=admin_headers,
        )
        assert resp.status_code == 200

    def test_update_fulfillment_404(
        self, client: TestClient, mock_cursor: MockCursor, admin_headers: dict,
    ) -> None:
        mock_cursor.rowcount = 0
        resp = client.put(
            "/api/v1/fulfillments/nonexistent",
            json={"status": "winner_notified"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_update_fulfillment_invalid_status_422(
        self, client: TestClient, admin_headers: dict,
    ) -> None:
        resp = client.put(
            "/api/v1/fulfillments/f1",
            json={"status": "invalid_status"},
            headers=admin_headers,
        )
        assert resp.status_code == 422


class TestDevRoutes:
    """Test /api/v1/dev endpoints."""

    def test_seed_201(self, client: TestClient) -> None:
        resp = client.post("/api/v1/dev/seed")
        assert resp.status_code == 201
        data = resp.json()
        assert "message" in data

    def test_reset_200(self, client: TestClient, mock_cursor: MockCursor) -> None:
        mock_cursor.rowcount = 0
        resp = client.post("/api/v1/dev/reset")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
