"""E2E test: create drawing → purchase tickets → execute → winner notified."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestDrawingFlow:
    """Full sweepstakes lifecycle through API endpoints."""

    @pytest.fixture
    def _mock_repos(self, patch_db_pool: Any, mock_cursor: Any) -> None:
        """Ensure DB pool is mocked for all tests."""

    def test_admin_creates_drawing(
        self,
        client: TestClient,
        _mock_repos: None,
        admin_headers: dict[str, str],
    ) -> None:
        """Admin can create a new drawing."""
        mock_svc = MagicMock()
        mock_svc.create_drawing.return_value = {
            "drawing_id": "d1",
            "title": "Weekly Gold",
            "drawing_type": "weekly",
            "status": "draft",
            "ticket_cost": 500,
            "scheduled_at": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
        }

        with patch(
            "fittrack.api.routes.drawings._get_drawing_service",
            return_value=mock_svc,
        ):
            close_time = datetime.now(UTC) + timedelta(days=7) - timedelta(minutes=5)
            resp = client.post(
                "/api/v1/drawings",
                json={
                    "name": "Weekly Gold",
                    "drawing_type": "weekly",
                    "ticket_cost_points": 500,
                    "drawing_time": (datetime.now(UTC) + timedelta(days=7)).isoformat(),
                    "ticket_sales_close": close_time.isoformat(),
                },
                headers=admin_headers,
            )
            assert resp.status_code in (200, 201)

    def test_admin_schedules_drawing(
        self,
        client: TestClient,
        _mock_repos: None,
        admin_headers: dict[str, str],
    ) -> None:
        """Admin can transition drawing from draft to scheduled."""
        mock_svc = MagicMock()
        mock_svc.schedule_drawing.return_value = {
            "drawing_id": "d1",
            "status": "scheduled",
        }

        with patch(
            "fittrack.api.routes.drawings._get_drawing_service",
            return_value=mock_svc,
        ):
            resp = client.post(
                "/api/v1/drawings/d1/schedule",
                headers=admin_headers,
            )
            assert resp.status_code == 200

    def test_user_purchases_ticket(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """User can purchase tickets for an open drawing."""
        mock_svc = MagicMock()
        mock_svc.purchase_tickets.return_value = {
            "ticket_ids": ["t1"],
            "drawing_id": "d1",
            "user_id": "test-user",
            "quantity": 1,
            "total_cost": 500,
        }

        with patch(
            "fittrack.api.routes.drawings._get_ticket_service",
            return_value=mock_svc,
        ):
            resp = client.post(
                "/api/v1/drawings/d1/tickets?quantity=1",
                headers=user_headers,
            )
            assert resp.status_code in (200, 201)

    def test_ticket_purchase_requires_auth(
        self,
        client: TestClient,
        _mock_repos: None,
    ) -> None:
        """Ticket purchase requires authentication."""
        resp = client.post(
            "/api/v1/drawings/d1/tickets?quantity=1",
        )
        assert resp.status_code in (401, 403)

    def test_drawing_execution_selects_winner(self) -> None:
        """Drawing executor should select winners via CSPRNG."""
        from fittrack.services.drawing_executor import DrawingExecutor

        executor = DrawingExecutor(
            drawing_repo=MagicMock(),
            ticket_repo=MagicMock(),
            prize_repo=MagicMock(),
            fulfillment_repo=MagicMock(),
        )

        snapshot = [
            {
                "ticket_id": f"t{i}",
                "user_id": f"u{i % 5}",
                "drawing_id": "d1",
                "ticket_number": i + 1,
                "is_winner": False,
            }
            for i in range(10)
        ]
        prizes = [{"prize_id": "p1", "name": "Gift Card", "quantity": 1, "rank": 1}]
        random_seed = "test-seed-abc123"

        winners = executor._select_winners(snapshot, prizes, random_seed)
        assert len(winners) >= 1
        assert winners[0]["ticket_id"] in [s["ticket_id"] for s in snapshot]

    def test_drawing_execution_one_win_per_user(self) -> None:
        """CSPRNG winner selection enforces one win per user."""
        from fittrack.services.drawing_executor import DrawingExecutor

        executor = DrawingExecutor(
            drawing_repo=MagicMock(),
            ticket_repo=MagicMock(),
            prize_repo=MagicMock(),
            fulfillment_repo=MagicMock(),
        )

        # Only 1 user with all tickets
        snapshot = [
            {
                "ticket_id": f"t{i}",
                "user_id": "u1",
                "drawing_id": "d1",
                "ticket_number": i + 1,
                "is_winner": False,
            }
            for i in range(5)
        ]
        prizes = [
            {"prize_id": "p1", "name": "Prize 1", "quantity": 1, "rank": 1},
            {"prize_id": "p2", "name": "Prize 2", "quantity": 1, "rank": 2},
        ]

        winners = executor._select_winners(snapshot, prizes, "seed")
        # Only 1 user, so at most 1 winner (one win per user)
        user_ids = [w["user_id"] for w in winners]
        assert len(set(user_ids)) == len(user_ids)

    def test_drawing_types_have_costs(self) -> None:
        """All drawing types should have ticket costs defined."""
        from fittrack.core.constants import DRAWING_TICKET_COSTS, DRAWING_TYPES

        for dtype in DRAWING_TYPES:
            assert dtype in DRAWING_TICKET_COSTS

    def test_ticket_sales_close_before_drawing(self) -> None:
        """Ticket sales should close before drawing time."""
        from fittrack.core.constants import TICKET_SALES_CLOSE_MINUTES_BEFORE

        assert TICKET_SALES_CLOSE_MINUTES_BEFORE == 5

    def test_list_drawings(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """Users can list available drawings."""
        mock_svc = MagicMock()
        mock_svc.list_drawings.return_value = {
            "items": [
                {
                    "drawing_id": "d1",
                    "title": "Weekly Gold",
                    "drawing_type": "weekly",
                    "status": "open",
                    "ticket_cost": 500,
                },
            ],
            "pagination": {"page": 1, "limit": 20, "total_items": 1},
        }

        with patch(
            "fittrack.api.routes.drawings._get_drawing_service",
            return_value=mock_svc,
        ):
            resp = client.get("/api/v1/drawings", headers=user_headers)
            assert resp.status_code == 200

    def test_winner_notification_trigger(self) -> None:
        """Winning should trigger a notification."""
        from fittrack.services.notifications import NotificationService

        mock_repo = MagicMock()
        mock_repo.create.return_value = "n1"
        svc = NotificationService(notification_repo=mock_repo, dev_mode=True)

        result = svc.notify_winner(
            user_id="winner-user",
            email="winner@example.com",
            prize_name="$100 Gift Card",
            drawing_name="Weekly Gold",
        )
        mock_repo.create.assert_called_once()
        assert result["user_id"] == "winner-user"
        assert result["notification_type"] == "winner_selected"

    def test_fulfillment_workflow(self) -> None:
        """Fulfillment statuses follow valid transitions."""
        from fittrack.core.constants import FULFILLMENT_STATUSES

        expected_order = [
            "pending",
            "winner_notified",
            "address_confirmed",
            "address_invalid",
            "shipped",
            "delivered",
            "forfeited",
        ]
        assert expected_order == FULFILLMENT_STATUSES

    def test_drawing_status_lifecycle(self) -> None:
        """Drawing statuses follow valid lifecycle."""
        from fittrack.core.constants import DRAWING_STATUSES

        assert "draft" in DRAWING_STATUSES
        assert "scheduled" in DRAWING_STATUSES
        assert "open" in DRAWING_STATUSES
        assert "closed" in DRAWING_STATUSES
        assert "completed" in DRAWING_STATUSES
        assert "cancelled" in DRAWING_STATUSES

    def test_view_user_tickets(
        self,
        client: TestClient,
        _mock_repos: None,
        user_headers: dict[str, str],
    ) -> None:
        """Users can view their purchased tickets."""
        mock_repo = MagicMock()
        mock_repo.find_by_field.return_value = [
            {
                "ticket_id": "t1",
                "drawing_id": "d1",
                "user_id": "test-user",
                "purchased_at": datetime.now(UTC).isoformat(),
            },
        ]
        mock_repo.count.return_value = 1

        with patch(
            "fittrack.api.routes.tickets._get_repo",
            return_value=mock_repo,
        ):
            resp = client.get("/api/v1/tickets", headers=user_headers)
            assert resp.status_code == 200
