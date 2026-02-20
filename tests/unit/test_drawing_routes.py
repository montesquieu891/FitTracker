"""Tests for drawing API routes — public browsing and admin lifecycle."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestPublicDrawingRoutes:
    """Test public /api/v1/drawings endpoints."""

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_list_drawings(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.list_drawings.return_value = {
            "items": [{"drawing_id": "d1", "name": "Daily Draw"}],
            "pagination": {"page": 1, "limit": 20, "total_items": 1, "total_pages": 1},
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_list_drawings_with_type_filter(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.list_drawings.return_value = {
            "items": [],
            "pagination": {"page": 1, "limit": 20, "total_items": 0, "total_pages": 1},
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings?drawing_type=daily")
        assert resp.status_code == 200
        mock_svc.list_drawings.assert_called_once_with(
            drawing_type="daily", status=None, page=1, limit=20
        )

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_list_invalid_type_returns_error(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        from fittrack.services.drawings import DrawingError

        mock_svc = MagicMock()
        mock_svc.list_drawings.side_effect = DrawingError("Invalid drawing type")
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings?drawing_type=bogus")
        assert resp.status_code == 400

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_drawing(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_drawing.return_value = {
            "drawing_id": "d1",
            "name": "Daily Draw",
            "prizes": [],
            "total_tickets": 0,
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/d1")
        assert resp.status_code == 200
        assert resp.json()["drawing_id"] == "d1"

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_drawing_not_found(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        from fittrack.services.drawings import DrawingError

        mock_svc = MagicMock()
        mock_svc.get_drawing.side_effect = DrawingError("not found", 404)
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/nope")
        assert resp.status_code == 404

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_results(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_results.return_value = {
            "drawing_id": "d1",
            "total_tickets": 100,
            "winners": [{"user_id": "u1"}],
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/d1/results")
        assert resp.status_code == 200
        assert resp.json()["total_tickets"] == 100

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_get_results_not_completed(
        self, mock_factory: MagicMock, client: TestClient
    ) -> None:
        from fittrack.services.drawings import DrawingError

        mock_svc = MagicMock()
        mock_svc.get_results.side_effect = DrawingError("not completed", 400)
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/d1/results")
        assert resp.status_code == 400


class TestTicketPurchaseRoutes:
    """Test ticket purchase endpoints (auth required)."""

    def test_purchase_requires_auth(self, client: TestClient) -> None:
        resp = client.post("/api/v1/drawings/d1/tickets")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.drawings._get_ticket_service")
    def test_purchase_success(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.purchase_tickets.return_value = {
            "purchase_id": "tx1",
            "drawing_id": "d1",
            "quantity": 1,
            "total_cost": 100,
            "tickets": [{"ticket_id": "t1"}],
            "new_balance": 400,
        }
        mock_factory.return_value = mock_svc
        resp = client.post("/api/v1/drawings/d1/tickets", headers=user_headers)
        assert resp.status_code == 201
        assert resp.json()["total_cost"] == 100

    @patch("fittrack.api.routes.drawings._get_ticket_service")
    def test_purchase_insufficient_balance(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        from fittrack.services.tickets import TicketError

        mock_svc = MagicMock()
        mock_svc.purchase_tickets.side_effect = TicketError("Insufficient points")
        mock_factory.return_value = mock_svc
        resp = client.post("/api/v1/drawings/d1/tickets", headers=user_headers)
        assert resp.status_code == 400

    @patch("fittrack.api.routes.drawings._get_ticket_service")
    def test_purchase_with_quantity(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.purchase_tickets.return_value = {
            "purchase_id": "tx1",
            "drawing_id": "d1",
            "quantity": 5,
            "total_cost": 500,
            "tickets": [{"ticket_id": f"t{i}"} for i in range(5)],
            "new_balance": 0,
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings/d1/tickets?quantity=5", headers=user_headers
        )
        assert resp.status_code == 201
        assert resp.json()["quantity"] == 5

    def test_my_tickets_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/drawings/d1/my-tickets")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.drawings._get_ticket_service")
    def test_my_tickets(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_user_tickets.return_value = {
            "drawing_id": "d1",
            "user_id": "test-user",
            "tickets": [],
            "count": 0,
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/drawings/d1/my-tickets", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["count"] == 0


class TestAdminDrawingRoutes:
    """Test admin drawing management endpoints."""

    def test_create_requires_admin(
        self, client: TestClient, user_headers: dict
    ) -> None:
        resp = client.post(
            "/api/v1/drawings",
            json={
                "drawing_type": "daily",
                "name": "Test",
                "ticket_cost_points": 100,
                "drawing_time": "2026-03-01T18:00:00Z",
                "ticket_sales_close": "2026-03-01T17:55:00Z",
            },
            headers=user_headers,
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_create_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.create_drawing.return_value = {
            "drawing_id": "d1",
            "drawing_type": "daily",
            "name": "Daily Draw",
            "status": "draft",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings",
            json={
                "drawing_type": "daily",
                "name": "Daily Draw",
                "ticket_cost_points": 100,
                "drawing_time": "2026-03-01T18:00:00Z",
                "ticket_sales_close": "2026-03-01T17:55:00Z",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "draft"

    @patch("fittrack.api.routes.drawings._get_executor")
    def test_execute_requires_admin(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        resp = client.post(
            "/api/v1/drawings/d1/execute", headers=user_headers
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.drawings._get_executor")
    def test_execute_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_executor = MagicMock()
        mock_executor.execute.return_value = {
            "drawing_id": "d1",
            "status": "completed",
            "total_tickets": 50,
            "winners": [{"user_id": "u1", "prize_id": "p1"}],
        }
        mock_factory.return_value = mock_executor
        resp = client.post(
            "/api/v1/drawings/d1/execute", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_schedule_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.schedule_drawing.return_value = {
            "drawing_id": "d1",
            "status": "scheduled",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings/d1/schedule", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "scheduled"

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_open_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.open_drawing.return_value = {
            "drawing_id": "d1",
            "status": "open",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings/d1/open", headers=admin_headers
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_close_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.close_drawing.return_value = {
            "drawing_id": "d1",
            "status": "closed",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings/d1/close", headers=admin_headers
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.drawings._get_drawing_service")
    def test_cancel_drawing(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.cancel_drawing.return_value = {
            "drawing_id": "d1",
            "status": "cancelled",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/drawings/d1/cancel", headers=admin_headers
        )
        assert resp.status_code == 200

    def test_delete_requires_admin(
        self, client: TestClient, user_headers: dict
    ) -> None:
        resp = client.delete(
            "/api/v1/drawings/d1", headers=user_headers
        )
        assert resp.status_code == 403
