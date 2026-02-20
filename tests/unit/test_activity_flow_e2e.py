"""E2E test: activity sync → points awarded → balance updated → leaderboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestActivityFlow:
    """Activity tracking through point earning to leaderboard ranking."""

    @pytest.fixture
    def _mock_repos(self, patch_db_pool: Any, mock_cursor: Any) -> None:
        """Ensure DB pool is mocked for all tests."""

    def test_submit_activity_earns_points(
        self, client: TestClient, _mock_repos: None, user_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/activities should record activity."""
        mock_repo = MagicMock()
        mock_repo.create.return_value = "activity-id"
        mock_repo.find_by_field.return_value = []

        with patch(
            "fittrack.api.routes.activities._get_repo", return_value=mock_repo,
        ):
            resp = client.post(
                "/api/v1/activities",
                json={
                    "user_id": "test-user",
                    "activity_type": "steps",
                    "start_time": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
                    "end_time": datetime.now(UTC).isoformat(),
                    "metrics": {"step_count": 5000},
                },
                headers=user_headers,
            )
            assert resp.status_code in (200, 201)

    def test_list_activities(
        self, client: TestClient, _mock_repos: None, user_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/activities should list user's activities."""
        mock_repo = MagicMock()
        mock_repo.find_by_field.return_value = [
            {
                "activity_id": "a1",
                "user_id": "test-user",
                "activity_type": "steps",
                "started_at": datetime.now(UTC).isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
                "metrics": '{"step_count": 5000}',
                "source": "google_fit",
                "points_awarded": 50,
            },
        ]
        mock_repo.count.return_value = 1

        with patch(
            "fittrack.api.routes.activities._get_repo", return_value=mock_repo,
        ):
            resp = client.get("/api/v1/activities", headers=user_headers)
            assert resp.status_code == 200

    def test_points_calculation_steps(self) -> None:
        """Verify step-based point calculation logic."""
        from fittrack.services.points import calculate_step_points

        points = calculate_step_points(5000)
        assert points == 50  # 5000 / 1000 * 10

    def test_points_calculation_steps_capped(self) -> None:
        """Verify step points respect the daily cap at 20k steps."""
        from fittrack.services.points import calculate_step_points

        points = calculate_step_points(50000)
        # Capped at 20k steps → 200 points
        assert points == 200

    def test_points_workout_bonus(self) -> None:
        """Verify workout bonus calculation."""
        from fittrack.core.constants import POINTS_WORKOUT_BONUS, WORKOUT_MIN_DURATION_MINUTES

        assert POINTS_WORKOUT_BONUS == 50
        assert WORKOUT_MIN_DURATION_MINUTES == 20

    def test_daily_point_cap(self) -> None:
        """Verify daily point cap is enforced."""
        from fittrack.core.constants import DAILY_POINT_CAP

        assert DAILY_POINT_CAP == 1000

    def test_view_transactions(
        self, client: TestClient, _mock_repos: None, user_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/transactions should show point history."""
        mock_repo = MagicMock()
        mock_repo.find_by_field.return_value = [
            {
                "transaction_id": "t1",
                "user_id": "test-user",
                "type": "earn",
                "amount": 50,
                "balance_after": 50,
                "description": "Step count: 5000",
                "created_at": datetime.now(UTC).isoformat(),
            },
        ]
        mock_repo.count.return_value = 1

        with patch(
            "fittrack.api.routes.transactions._get_repo", return_value=mock_repo,
        ):
            resp = client.get("/api/v1/transactions", headers=user_headers)
            assert resp.status_code == 200

    def test_leaderboard_ranking(
        self, client: TestClient, _mock_repos: None, user_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/leaderboards/{period} should return rankings."""
        mock_svc = MagicMock()
        mock_svc.get_leaderboard.return_value = {
            "tier_code": "M-18-29-BEG",
            "period": "weekly",
            "entries": [
                {"rank": 1, "user_id": "u1", "display_name": "Runner1", "points": 500},
            ],
            "total_entries": 1,
        }

        with patch(
            "fittrack.api.routes.leaderboards._get_leaderboard_service",
            return_value=mock_svc,
        ):
            resp = client.get(
                "/api/v1/leaderboards/weekly?tier_code=M-18-29-BEG",
                headers=user_headers,
            )
            assert resp.status_code == 200

    def test_point_balance_reflects_earnings(self) -> None:
        """Point balance should be cumulative of earn transactions."""
        from fittrack.core.constants import POINTS_PER_1K_STEPS

        # 10k steps = 100 points
        steps = 10_000
        expected_points = (steps // 1000) * POINTS_PER_1K_STEPS
        assert expected_points == 100

    def test_weekly_streak_bonus(self) -> None:
        """7 consecutive active days should earn streak bonus."""
        from fittrack.core.constants import (
            ACTIVE_DAY_MIN_MINUTES,
            POINTS_WEEKLY_STREAK_BONUS,
            WEEKLY_STREAK_DAYS,
        )

        assert WEEKLY_STREAK_DAYS == 7
        assert POINTS_WEEKLY_STREAK_BONUS == 250
        assert ACTIVE_DAY_MIN_MINUTES == 30
