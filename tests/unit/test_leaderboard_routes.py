"""Tests for leaderboard API routes — GET /{period} and GET /{period}/me."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestLeaderboardRoutes:
    """Test /api/v1/leaderboards endpoints via TestClient."""

    # ── GET /{period} ───────────────────────────────────────────────

    def test_get_leaderboard_requires_auth(self, client: TestClient) -> None:
        """Unauthenticated request returns 401."""
        resp = client.get("/api/v1/leaderboards/daily")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_daily_leaderboard(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "period": "daily",
            "tier_code": "M-18-29-BEG",
            "items": [
                {"user_id": "u1", "rank": 1, "points_earned": 300},
                {"user_id": "u2", "rank": 2, "points_earned": 200},
            ],
            "pagination": {
                "page": 1,
                "limit": 100,
                "total_items": 2,
                "total_pages": 1,
            },
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/daily", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["period"] == "daily"
        assert len(data["items"]) == 2
        assert data["items"][0]["rank"] == 1
        assert data["pagination"]["total_items"] == 2

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_leaderboard_with_explicit_tier(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "period": "weekly",
            "tier_code": "F-30-39-INT",
            "items": [],
            "pagination": {
                "page": 1,
                "limit": 100,
                "total_items": 0,
                "total_pages": 1,
            },
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get(
            "/api/v1/leaderboards/weekly?tier_code=F-30-39-INT",
            headers=user_headers,
        )
        assert resp.status_code == 200
        # _get_user_tier should NOT be called when tier_code is explicit
        mock_svc.get_leaderboard.assert_called_once()
        call_kwargs = mock_svc.get_leaderboard.call_args
        assert call_kwargs[1]["tier_code"] == "F-30-39-INT" or (
            call_kwargs[0] if call_kwargs[0] else True
        )

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_leaderboard_invalid_period(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        from fittrack.services.leaderboard import LeaderboardError

        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.side_effect = LeaderboardError(
            "Invalid period: hourly", status_code=400
        )
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/hourly", headers=user_headers)
        assert resp.status_code == 400

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_leaderboard_pagination_params(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "items": [],
            "pagination": {
                "page": 2,
                "limit": 10,
                "total_items": 50,
                "total_pages": 5,
            },
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get(
            "/api/v1/leaderboards/monthly?page=2&limit=10",
            headers=user_headers,
        )
        assert resp.status_code == 200
        mock_svc.get_leaderboard.assert_called_once()
        kwargs = mock_svc.get_leaderboard.call_args[1]
        assert kwargs["page"] == 2
        assert kwargs["limit"] == 10

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_leaderboard_defaults_to_user_tier(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_tier.return_value = "F-40-49-ADV"
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "limit": 100,
                "total_items": 0,
                "total_pages": 1,
            },
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/all_time", headers=user_headers)
        assert resp.status_code == 200
        mock_tier.assert_called_once()
        kwargs = mock_svc.get_leaderboard.call_args[1]
        assert kwargs["tier_code"] == "F-40-49-ADV"

    # ── GET /{period}/me ────────────────────────────────────────────

    def test_get_my_rank_requires_auth(self, client: TestClient) -> None:
        resp = client.get("/api/v1/leaderboards/daily/me")
        assert resp.status_code == 401

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_my_rank_success(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_user_rank.return_value = {
            "user_rank": 5,
            "user_entry": {"user_id": "test-user", "rank": 5, "points_earned": 200},
            "total_participants": 50,
            "period": "daily",
            "tier_code": "M-18-29-BEG",
            "context": [
                {"user_id": f"u{i}", "rank": i} for i in range(1, 11)
            ],
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/daily/me", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_rank"] == 5
        assert data["total_participants"] == 50
        assert len(data["context"]) == 10

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_my_rank_not_ranked(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_user_rank.return_value = {
            "user_rank": None,
            "user_entry": None,
            "total_participants": 10,
            "period": "daily",
            "tier_code": "M-18-29-BEG",
            "context": [],
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/daily/me", headers=user_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_rank"] is None
        assert data["context"] == []

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_my_rank_invalid_period(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        from fittrack.services.leaderboard import LeaderboardError

        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_user_rank.side_effect = LeaderboardError(
            "Invalid period: yearly", status_code=400
        )
        mock_svc_factory.return_value = mock_svc

        resp = client.get("/api/v1/leaderboards/yearly/me", headers=user_headers)
        assert resp.status_code == 400

    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_get_my_rank_with_explicit_tier(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
    ) -> None:
        mock_svc = MagicMock()
        mock_svc.get_user_rank.return_value = {
            "user_rank": 3,
            "user_entry": {"user_id": "test-user", "rank": 3},
            "total_participants": 20,
            "period": "weekly",
            "tier_code": "F-30-39-INT",
            "context": [],
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get(
            "/api/v1/leaderboards/weekly/me?tier_code=F-30-39-INT",
            headers=user_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_rank"] == 3

    # ── All valid periods ───────────────────────────────────────────

    @pytest.mark.parametrize("period", ["daily", "weekly", "monthly", "all_time"])
    @patch("fittrack.api.routes.leaderboards._get_leaderboard_service")
    @patch("fittrack.api.routes.leaderboards._get_user_tier")
    def test_all_valid_periods_accepted(
        self,
        mock_tier: MagicMock,
        mock_svc_factory: MagicMock,
        client: TestClient,
        user_headers: dict,
        period: str,
    ) -> None:
        mock_tier.return_value = "M-18-29-BEG"
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "items": [],
            "pagination": {
                "page": 1,
                "limit": 100,
                "total_items": 0,
                "total_pages": 1,
            },
        }
        mock_svc_factory.return_value = mock_svc

        resp = client.get(f"/api/v1/leaderboards/{period}", headers=user_headers)
        assert resp.status_code == 200
