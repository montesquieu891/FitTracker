"""Tests for fulfillment API routes — admin lifecycle and winner address."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestFulfillmentListRoute:
    """Test GET /api/v1/fulfillments (admin)."""

    def test_list_requires_admin(
        self, client: TestClient, user_headers: dict
    ) -> None:
        resp = client.get("/api/v1/fulfillments", headers=user_headers)
        assert resp.status_code == 403

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_list_fulfillments(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.list_fulfillments.return_value = {
            "items": [{"fulfillment_id": "f1", "status": "pending"}],
            "pagination": {
                "page": 1, "limit": 20, "total_items": 1, "total_pages": 1
            },
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/fulfillments", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1


class TestFulfillmentGetRoute:
    """Test GET /api/v1/fulfillments/{id} (admin)."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_get_fulfillment(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_fulfillment.return_value = {
            "fulfillment_id": "f1",
            "status": "pending",
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/fulfillments/f1", headers=admin_headers)
        assert resp.status_code == 200

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_get_not_found(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        from fittrack.services.fulfillments import FulfillmentError

        mock_svc = MagicMock()
        mock_svc.get_fulfillment.side_effect = FulfillmentError("not found", 404)
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/fulfillments/nope", headers=admin_headers)
        assert resp.status_code == 404


class TestNotifyRoute:
    """Test POST /api/v1/fulfillments/{id}/notify (admin)."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_notify_winner(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.notify_winner.return_value = {
            "fulfillment_id": "f1",
            "status": "winner_notified",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/notify", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "winner_notified"


class TestShipRoute:
    """Test POST /api/v1/fulfillments/{id}/ship (admin)."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_ship_prize(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.ship_prize.return_value = {
            "fulfillment_id": "f1",
            "status": "shipped",
            "carrier": "UPS",
            "tracking_number": "1Z123",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/ship?carrier=UPS&tracking_number=1Z123",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "shipped"


class TestDeliverRoute:
    """Test POST /api/v1/fulfillments/{id}/deliver (admin)."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_mark_delivered(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.mark_delivered.return_value = {
            "fulfillment_id": "f1",
            "status": "delivered",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/deliver", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "delivered"


class TestForfeitRoute:
    """Test POST /api/v1/fulfillments/{id}/forfeit (admin)."""

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_forfeit(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.forfeit.return_value = {
            "fulfillment_id": "f1",
            "status": "forfeited",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/forfeit", headers=admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "forfeited"


class TestConfirmAddressRoute:
    """Test POST /api/v1/fulfillments/{id}/confirm-address (winner)."""

    def test_requires_auth(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/fulfillments/f1/confirm-address",
            json={"street": "x", "city": "x", "state": "x", "zip_code": "x"},
        )
        assert resp.status_code == 401

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_wrong_user_is_forbidden(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_fulfillment.return_value = {
            "fulfillment_id": "f1",
            "user_id": "other-user",
            "status": "winner_notified",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/confirm-address",
            json={"street": "x", "city": "x", "state": "x", "zip_code": "x"},
            headers=user_headers,
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.fulfillments._get_service")
    def test_confirm_address_success(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_fulfillment.return_value = {
            "fulfillment_id": "f1",
            "user_id": "test-user",
            "status": "winner_notified",
        }
        mock_svc.confirm_address.return_value = {
            "fulfillment_id": "f1",
            "status": "address_confirmed",
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/fulfillments/f1/confirm-address",
            json={
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip_code": "90210",
            },
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "address_confirmed"
