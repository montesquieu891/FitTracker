"""Analytics service — dashboard metrics and trend queries.

Provides overview metrics (MAU, DAU, total users, active drawings),
registration trends, activity metrics, and drawing participation stats.
All queries operate on repository abstractions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.core.constants import ACTIVITY_TYPES, DRAWING_TYPES

logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    """Raised on analytics query failures."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


VALID_TREND_PERIODS = ("daily", "weekly", "monthly")


class AnalyticsService:
    """Service for computing analytics and dashboard metrics."""

    def __init__(
        self,
        user_repo: Any,
        activity_repo: Any,
        drawing_repo: Any,
        ticket_repo: Any,
        transaction_repo: Any,
    ) -> None:
        self.user_repo = user_repo
        self.activity_repo = activity_repo
        self.drawing_repo = drawing_repo
        self.ticket_repo = ticket_repo
        self.transaction_repo = transaction_repo

    # ── Overview ─────────────────────────────────────────────────

    def get_overview(
        self, now: datetime | None = None
    ) -> dict[str, Any]:
        """Dashboard overview metrics."""
        if now is None:
            now = datetime.now(tz=UTC)

        total_users = self.user_repo.count()
        active_users = self.user_repo.count(
            filters={"status": "active"}
        )
        suspended_users = self.user_repo.count(
            filters={"status": "suspended"}
        )
        banned_users = self.user_repo.count(
            filters={"status": "banned"}
        )
        pending_users = self.user_repo.count(
            filters={"status": "pending"}
        )

        # Active drawings (open or scheduled)
        open_drawings = self.drawing_repo.count(
            filters={"status": "open"}
        )
        scheduled_drawings = self.drawing_repo.count(
            filters={"status": "scheduled"}
        )
        completed_drawings = self.drawing_repo.count(
            filters={"status": "completed"}
        )

        # DAU/MAU approximation from activity data
        today_start = now.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        # Get daily active users from activities
        daily_activities = self.activity_repo.find_all(
            limit=10000, offset=0
        )
        dau_users = set()
        mau_users = set()
        for act in daily_activities:
            created = act.get("created_at") or act.get("start_time")
            user_id = act.get("user_id")
            if not created or not user_id:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if hasattr(created, "tzinfo") and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created >= today_start:
                dau_users.add(user_id)
            if created >= month_start:
                mau_users.add(user_id)

        return {
            "total_users": total_users,
            "active_users": active_users,
            "suspended_users": suspended_users,
            "banned_users": banned_users,
            "pending_users": pending_users,
            "dau": len(dau_users),
            "mau": len(mau_users),
            "open_drawings": open_drawings,
            "scheduled_drawings": scheduled_drawings,
            "completed_drawings": completed_drawings,
            "generated_at": now.isoformat(),
        }

    # ── Registration Trends ──────────────────────────────────────

    def get_registration_trends(
        self,
        period: str = "daily",
        days: int = 30,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Registration trends over time.

        Returns counts bucketed by the specified period.
        """
        if period not in VALID_TREND_PERIODS:
            raise AnalyticsError(
                f"Invalid period: {period}. Valid: "
                f"{list(VALID_TREND_PERIODS)}",
                400,
            )

        if now is None:
            now = datetime.now(tz=UTC)

        start_date = now - timedelta(days=days)

        # Fetch all users and bucket by created_at
        all_users = self.user_repo.find_all(limit=50000, offset=0)
        buckets: dict[str, int] = {}

        for user in all_users:
            created = user.get("created_at")
            if not created:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if hasattr(created, "tzinfo") and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created < start_date:
                continue

            bucket_key = self._get_bucket_key(created, period)
            buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

        # Sort by bucket key
        sorted_buckets = sorted(buckets.items())

        return {
            "period": period,
            "days": days,
            "data": [
                {"date": k, "count": v} for k, v in sorted_buckets
            ],
            "total": sum(buckets.values()),
        }

    @staticmethod
    def _get_bucket_key(dt: datetime, period: str) -> str:
        """Get the bucket key for grouping."""
        if period == "daily":
            return dt.strftime("%Y-%m-%d")
        if period == "weekly":
            # ISO week
            return dt.strftime("%Y-W%W")
        if period == "monthly":
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y-%m-%d")

    # ── Activity Metrics ─────────────────────────────────────────

    def get_activity_metrics(
        self, days: int = 30, now: datetime | None = None
    ) -> dict[str, Any]:
        """Activity metrics: averages, by type, by tier."""
        if now is None:
            now = datetime.now(tz=UTC)

        start_date = now - timedelta(days=days)

        all_activities = self.activity_repo.find_all(
            limit=50000, offset=0
        )

        # Filter to date range
        activities = []
        for act in all_activities:
            created = act.get("created_at") or act.get("start_time")
            if not created:
                activities.append(act)
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    activities.append(act)
                    continue
            if hasattr(created, "tzinfo") and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if created >= start_date:
                activities.append(act)

        total = len(activities)
        user_ids = {a.get("user_id") for a in activities if a.get("user_id")}
        users_with_activity = len(user_ids)
        avg_per_user = (
            round(total / users_with_activity, 1) if users_with_activity else 0
        )

        # By type
        by_type: dict[str, int] = {t: 0 for t in ACTIVITY_TYPES}
        for act in activities:
            atype = act.get("activity_type", "unknown")
            if atype in by_type:
                by_type[atype] += 1
            else:
                by_type[atype] = 1

        return {
            "period_days": days,
            "total_activities": total,
            "users_with_activity": users_with_activity,
            "avg_per_user": avg_per_user,
            "by_type": by_type,
            "generated_at": now.isoformat(),
        }

    # ── Drawing Metrics ──────────────────────────────────────────

    def get_drawing_metrics(
        self, now: datetime | None = None
    ) -> dict[str, Any]:
        """Drawing participation and ticket purchase metrics."""
        if now is None:
            now = datetime.now(tz=UTC)

        # Get all drawings
        all_drawings = self.drawing_repo.find_all(limit=10000, offset=0)
        total_drawings = len(all_drawings)

        # By type
        by_type: dict[str, int] = {t: 0 for t in DRAWING_TYPES}
        by_status: dict[str, int] = {}
        completed_ids: list[str] = []

        for d in all_drawings:
            dtype = d.get("drawing_type", "unknown")
            dstatus = d.get("status", "unknown")
            if dtype in by_type:
                by_type[dtype] += 1
            by_status[dstatus] = by_status.get(dstatus, 0) + 1
            if dstatus == "completed":
                did = d.get("drawing_id")
                if did:
                    completed_ids.append(did)

        # Get all tickets
        all_tickets = self.ticket_repo.find_all(limit=50000, offset=0)
        total_tickets = len(all_tickets)
        ticket_users = {
            t.get("user_id") for t in all_tickets if t.get("user_id")
        }
        unique_participants = len(ticket_users)

        # Participation rate
        total_users = self.user_repo.count(filters={"status": "active"})
        participation_rate = (
            round(unique_participants / total_users * 100, 1)
            if total_users
            else 0
        )

        avg_tickets_per_user = (
            round(total_tickets / unique_participants, 1)
            if unique_participants
            else 0
        )

        return {
            "total_drawings": total_drawings,
            "by_type": by_type,
            "by_status": by_status,
            "total_tickets_sold": total_tickets,
            "unique_participants": unique_participants,
            "participation_rate": participation_rate,
            "avg_tickets_per_user": avg_tickets_per_user,
            "completed_drawings": len(completed_ids),
            "generated_at": now.isoformat(),
        }
