"""Tests for analytics service — metric queries with mock data."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from fittrack.services.analytics import (
    AnalyticsError,
    AnalyticsService,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_service(
    *,
    users: list[dict[str, Any]] | None = None,
    activities: list[dict[str, Any]] | None = None,
    drawings: list[dict[str, Any]] | None = None,
    tickets: list[dict[str, Any]] | None = None,
) -> AnalyticsService:
    """Create an AnalyticsService with mock repos."""
    user_repo = MagicMock()
    activity_repo = MagicMock()
    drawing_repo = MagicMock()
    ticket_repo = MagicMock()
    transaction_repo = MagicMock()

    user_repo.find_all.return_value = users or []
    user_repo.count.side_effect = lambda filters=None: (
        len([
            u for u in (users or [])
            if not filters or all(
                u.get(k) == v for k, v in filters.items()
            )
        ])
    )

    activity_repo.find_all.return_value = activities or []
    drawing_repo.find_all.return_value = drawings or []
    drawing_repo.count.side_effect = lambda filters=None: (
        len([
            d for d in (drawings or [])
            if not filters or all(
                d.get(k) == v for k, v in filters.items()
            )
        ])
    )
    ticket_repo.find_all.return_value = tickets or []

    return AnalyticsService(
        user_repo=user_repo,
        activity_repo=activity_repo,
        drawing_repo=drawing_repo,
        ticket_repo=ticket_repo,
        transaction_repo=transaction_repo,
    )


NOW = datetime(2026, 2, 20, 12, 0, 0, tzinfo=UTC)


# ── Overview Tests ───────────────────────────────────────────────────


class TestOverview:
    """Test dashboard overview metrics."""

    def test_overview_empty(self) -> None:
        svc = _make_service()
        result = svc.get_overview(now=NOW)
        assert result["total_users"] == 0
        assert result["dau"] == 0
        assert result["mau"] == 0
        assert result["open_drawings"] == 0

    def test_overview_with_users(self) -> None:
        users = [
            {"user_id": "u1", "status": "active", "email": "a@b.com"},
            {"user_id": "u2", "status": "active", "email": "c@d.com"},
            {"user_id": "u3", "status": "suspended", "email": "e@f.com"},
            {"user_id": "u4", "status": "banned", "email": "g@h.com"},
            {"user_id": "u5", "status": "pending", "email": "i@j.com"},
        ]
        svc = _make_service(users=users)
        result = svc.get_overview(now=NOW)
        assert result["total_users"] == 5
        assert result["active_users"] == 2
        assert result["suspended_users"] == 1
        assert result["banned_users"] == 1
        assert result["pending_users"] == 1

    def test_overview_with_drawings(self) -> None:
        drawings = [
            {"drawing_id": "d1", "status": "open", "drawing_type": "daily"},
            {"drawing_id": "d2", "status": "scheduled", "drawing_type": "weekly"},
            {"drawing_id": "d3", "status": "completed", "drawing_type": "monthly"},
        ]
        svc = _make_service(drawings=drawings)
        result = svc.get_overview(now=NOW)
        assert result["open_drawings"] == 1
        assert result["scheduled_drawings"] == 1
        assert result["completed_drawings"] == 1

    def test_overview_dau_mau(self) -> None:
        today = NOW.replace(hour=6)
        week_ago = NOW - timedelta(days=5)
        activities = [
            {"user_id": "u1", "created_at": today.isoformat()},
            {"user_id": "u2", "created_at": week_ago.isoformat()},
        ]
        svc = _make_service(activities=activities)
        result = svc.get_overview(now=NOW)
        assert result["dau"] == 1  # only today
        assert result["mau"] == 2  # both within month

    def test_overview_generated_at(self) -> None:
        svc = _make_service()
        result = svc.get_overview(now=NOW)
        assert result["generated_at"] == NOW.isoformat()


# ── Registration Trends Tests ────────────────────────────────────────


class TestRegistrationTrends:
    """Test registration trend queries."""

    def test_daily_trends(self) -> None:
        users = [
            {"user_id": "u1", "created_at": (NOW - timedelta(days=1)).isoformat()},
            {"user_id": "u2", "created_at": (NOW - timedelta(days=1)).isoformat()},
            {"user_id": "u3", "created_at": NOW.isoformat()},
        ]
        svc = _make_service(users=users)
        result = svc.get_registration_trends(period="daily", days=7, now=NOW)
        assert result["period"] == "daily"
        assert result["total"] == 3

    def test_weekly_trends(self) -> None:
        users = [
            {"user_id": "u1", "created_at": NOW.isoformat()},
        ]
        svc = _make_service(users=users)
        result = svc.get_registration_trends(period="weekly", days=30, now=NOW)
        assert result["period"] == "weekly"
        assert len(result["data"]) >= 1

    def test_monthly_trends(self) -> None:
        users = [
            {"user_id": "u1", "created_at": NOW.isoformat()},
        ]
        svc = _make_service(users=users)
        result = svc.get_registration_trends(period="monthly", days=90, now=NOW)
        assert result["period"] == "monthly"

    def test_invalid_period(self) -> None:
        svc = _make_service()
        with pytest.raises(AnalyticsError, match="Invalid period"):
            svc.get_registration_trends(period="yearly", now=NOW)

    def test_filters_by_date_range(self) -> None:
        users = [
            {"user_id": "u1", "created_at": (NOW - timedelta(days=100)).isoformat()},
            {"user_id": "u2", "created_at": NOW.isoformat()},
        ]
        svc = _make_service(users=users)
        result = svc.get_registration_trends(days=7, now=NOW)
        # Only recent user should be in data
        assert result["total"] == 1

    def test_bucket_key_daily(self) -> None:
        key = AnalyticsService._get_bucket_key(NOW, "daily")
        assert key == "2026-02-20"

    def test_bucket_key_monthly(self) -> None:
        key = AnalyticsService._get_bucket_key(NOW, "monthly")
        assert key == "2026-02"

    def test_empty_trends(self) -> None:
        svc = _make_service()
        result = svc.get_registration_trends(now=NOW)
        assert result["total"] == 0
        assert result["data"] == []


# ── Activity Metrics Tests ───────────────────────────────────────────


class TestActivityMetrics:
    """Test activity metric queries."""

    def test_empty_activities(self) -> None:
        svc = _make_service()
        result = svc.get_activity_metrics(now=NOW)
        assert result["total_activities"] == 0
        assert result["users_with_activity"] == 0
        assert result["avg_per_user"] == 0

    def test_with_activities(self) -> None:
        activities = [
            {"user_id": "u1", "activity_type": "steps", "created_at": NOW.isoformat()},
            {"user_id": "u1", "activity_type": "workout", "created_at": NOW.isoformat()},
            {"user_id": "u2", "activity_type": "steps", "created_at": NOW.isoformat()},
        ]
        svc = _make_service(activities=activities)
        result = svc.get_activity_metrics(now=NOW)
        assert result["total_activities"] == 3
        assert result["users_with_activity"] == 2
        assert result["avg_per_user"] == 1.5

    def test_by_type_breakdown(self) -> None:
        activities = [
            {"user_id": "u1", "activity_type": "steps", "created_at": NOW.isoformat()},
            {"user_id": "u1", "activity_type": "steps", "created_at": NOW.isoformat()},
            {"user_id": "u2", "activity_type": "workout", "created_at": NOW.isoformat()},
            {
                "user_id": "u3",
                "activity_type": "active_minutes",
                "created_at": NOW.isoformat(),
            },
        ]
        svc = _make_service(activities=activities)
        result = svc.get_activity_metrics(now=NOW)
        assert result["by_type"]["steps"] == 2
        assert result["by_type"]["workout"] == 1
        assert result["by_type"]["active_minutes"] == 1

    def test_generated_at(self) -> None:
        svc = _make_service()
        result = svc.get_activity_metrics(now=NOW)
        assert result["generated_at"] == NOW.isoformat()


# ── Drawing Metrics Tests ────────────────────────────────────────────


class TestDrawingMetrics:
    """Test drawing participation metrics."""

    def test_empty_drawings(self) -> None:
        svc = _make_service()
        result = svc.get_drawing_metrics(now=NOW)
        assert result["total_drawings"] == 0
        assert result["total_tickets_sold"] == 0
        assert result["unique_participants"] == 0

    def test_with_drawings_and_tickets(self) -> None:
        drawings = [
            {"drawing_id": "d1", "drawing_type": "daily", "status": "completed"},
            {"drawing_id": "d2", "drawing_type": "weekly", "status": "open"},
        ]
        tickets = [
            {"ticket_id": "t1", "user_id": "u1", "drawing_id": "d1"},
            {"ticket_id": "t2", "user_id": "u1", "drawing_id": "d1"},
            {"ticket_id": "t3", "user_id": "u2", "drawing_id": "d2"},
        ]
        users = [
            {"user_id": "u1", "status": "active"},
            {"user_id": "u2", "status": "active"},
            {"user_id": "u3", "status": "active"},
        ]
        svc = _make_service(users=users, drawings=drawings, tickets=tickets)
        result = svc.get_drawing_metrics(now=NOW)
        assert result["total_drawings"] == 2
        assert result["total_tickets_sold"] == 3
        assert result["unique_participants"] == 2
        assert result["avg_tickets_per_user"] == 1.5

    def test_by_type_breakdown(self) -> None:
        drawings = [
            {"drawing_id": "d1", "drawing_type": "daily", "status": "open"},
            {"drawing_id": "d2", "drawing_type": "daily", "status": "completed"},
            {"drawing_id": "d3", "drawing_type": "weekly", "status": "open"},
        ]
        svc = _make_service(drawings=drawings)
        result = svc.get_drawing_metrics(now=NOW)
        assert result["by_type"]["daily"] == 2
        assert result["by_type"]["weekly"] == 1

    def test_by_status_breakdown(self) -> None:
        drawings = [
            {"drawing_id": "d1", "drawing_type": "daily", "status": "open"},
            {"drawing_id": "d2", "drawing_type": "daily", "status": "completed"},
            {"drawing_id": "d3", "drawing_type": "daily", "status": "completed"},
        ]
        svc = _make_service(drawings=drawings)
        result = svc.get_drawing_metrics(now=NOW)
        assert result["by_status"]["open"] == 1
        assert result["by_status"]["completed"] == 2

    def test_participation_rate(self) -> None:
        users = [
            {"user_id": "u1", "status": "active"},
            {"user_id": "u2", "status": "active"},
            {"user_id": "u3", "status": "active"},
            {"user_id": "u4", "status": "active"},
        ]
        tickets = [
            {"ticket_id": "t1", "user_id": "u1"},
            {"ticket_id": "t2", "user_id": "u2"},
        ]
        svc = _make_service(users=users, tickets=tickets)
        result = svc.get_drawing_metrics(now=NOW)
        assert result["participation_rate"] == 50.0

    def test_no_active_users_rate(self) -> None:
        svc = _make_service()
        result = svc.get_drawing_metrics(now=NOW)
        assert result["participation_rate"] == 0
