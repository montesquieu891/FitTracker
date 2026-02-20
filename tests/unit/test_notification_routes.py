"""Tests for notification routes — endpoint responses."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


class TestListNotifications:
    """Test GET /api/v1/notifications."""

    @patch("fittrack.api.routes.notifications._get_service")
    def test_requires_auth(self, mock_factory: MagicMock, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.notifications._get_service")
    def test_list_notifications(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_user_notifications.return_value = {
            "items": [
                {
                    "notification_id": "n1",
                    "title": "Test",
                    "is_read": 0,
                }
            ],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total_items": 1,
                "total_pages": 1,
            },
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/notifications", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1


class TestUnreadCount:
    """Test GET /api/v1/notifications/unread-count."""

    @patch("fittrack.api.routes.notifications._get_service")
    def test_requires_auth(self, mock_factory: MagicMock, client: TestClient) -> None:
        resp = client.get("/api/v1/notifications/unread-count")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.notifications._get_service")
    def test_unread_count(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_unread_count.return_value = 3
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/notifications/unread-count",
            headers=user_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["unread_count"] == 3


class TestGetNotification:
    """Test GET /api/v1/notifications/{id}."""

    @patch("fittrack.api.routes.notifications._get_service")
    def test_get_notification(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_notification.return_value = {
            "notification_id": "n1",
            "user_id": "test-user",
            "title": "Hello",
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/notifications/n1", headers=user_headers)
        assert resp.status_code == 200

    @patch("fittrack.api.routes.notifications._get_service")
    def test_get_notification_wrong_user(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_notification.return_value = {
            "notification_id": "n1",
            "user_id": "other-user",
            "title": "Private",
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/notifications/n1", headers=user_headers)
        assert resp.status_code == 403

    @patch("fittrack.api.routes.notifications._get_service")
    def test_get_not_found(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        from fittrack.services.notifications import NotificationError

        mock_svc = MagicMock()
        mock_svc.get_notification.side_effect = NotificationError("not found", 404)
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/notifications/n999", headers=user_headers)
        assert resp.status_code == 404


class TestMarkAsRead:
    """Test PUT /api/v1/notifications/{id}/read."""

    @patch("fittrack.api.routes.notifications._get_service")
    def test_requires_auth(self, mock_factory: MagicMock, client: TestClient) -> None:
        resp = client.put("/api/v1/notifications/n1/read")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.notifications._get_service")
    def test_mark_as_read(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.mark_as_read.return_value = {
            "notification_id": "n1",
            "is_read": True,
        }
        mock_factory.return_value = mock_svc
        resp = client.put("/api/v1/notifications/n1/read", headers=user_headers)
        assert resp.status_code == 200
        assert resp.json()["is_read"] is True

    @patch("fittrack.api.routes.notifications._get_service")
    def test_mark_not_found(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        from fittrack.services.notifications import NotificationError

        mock_svc = MagicMock()
        mock_svc.mark_as_read.side_effect = NotificationError("not found", 404)
        mock_factory.return_value = mock_svc
        resp = client.put("/api/v1/notifications/n999/read", headers=user_headers)
        assert resp.status_code == 404


class TestAdminUserRoutes:
    """Test admin user management routes."""

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_search_requires_admin(self, mock_factory: MagicMock, client: TestClient) -> None:
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_search_users(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.search_users.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total_items": 0,
                "total_pages": 1,
            },
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/admin/users", headers=admin_headers)
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_search_with_filters(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.search_users.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total_items": 0,
                "total_pages": 1,
            },
        }
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/users?status=active&role=user",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_change_status_requires_admin(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.put(
            "/api/v1/admin/users/u1/status?new_status=suspended",
            headers=user_headers,
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_change_status(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.change_user_status.return_value = {
            "user_id": "u1",
            "old_status": "active",
            "new_status": "suspended",
        }
        mock_factory.return_value = mock_svc
        resp = client.put(
            "/api/v1/admin/users/u1/status?new_status=suspended",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_adjust_points_requires_admin(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        user_headers: dict[str, str],
    ) -> None:
        resp = client.post(
            "/api/v1/admin/users/u1/adjust-points?amount=100&reason=test",
            headers=user_headers,
        )
        assert resp.status_code == 403

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_adjust_points(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.adjust_points.return_value = {
            "user_id": "u1",
            "amount": 100,
            "new_balance": 600,
        }
        mock_factory.return_value = mock_svc
        resp = client.post(
            "/api/v1/admin/users/u1/adjust-points?amount=100&reason=bonus",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_users._get_service")
    def test_get_user_detail(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_user_detail.return_value = {
            "user_id": "u1",
            "email": "a@b.com",
        }
        mock_factory.return_value = mock_svc
        resp = client.get("/api/v1/admin/users/u1", headers=admin_headers)
        assert resp.status_code == 200


class TestAnalyticsRoutes:
    """Test admin analytics routes."""

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_overview_requires_admin(self, mock_factory: MagicMock, client: TestClient) -> None:
        resp = client.get("/api/v1/admin/analytics/overview")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_overview(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_overview.return_value = {
            "total_users": 100,
            "dau": 10,
        }
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/analytics/overview",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total_users"] == 100

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_registrations(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_registration_trends.return_value = {
            "period": "daily",
            "data": [],
            "total": 0,
        }
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/analytics/registrations",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_activity_metrics(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_activity_metrics.return_value = {
            "total_activities": 50,
        }
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/analytics/activity",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_drawing_metrics(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_drawing_metrics.return_value = {
            "total_drawings": 5,
        }
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/analytics/drawings",
            headers=admin_headers,
        )
        assert resp.status_code == 200

    @patch("fittrack.api.routes.admin_analytics._get_service")
    def test_registrations_invalid_period(
        self,
        mock_factory: MagicMock,
        client: TestClient,
        admin_headers: dict[str, str],
    ) -> None:
        from fittrack.services.analytics import AnalyticsError

        mock_svc = MagicMock()
        mock_svc.get_registration_trends.side_effect = AnalyticsError("Invalid period", 400)
        mock_factory.return_value = mock_svc
        resp = client.get(
            "/api/v1/admin/analytics/registrations?period=yearly",
            headers=admin_headers,
        )
        assert resp.status_code == 400
