"""Daily points log repository — tracks per-day point earnings for cap enforcement."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class DailyPointsLogRepository(BaseRepository):
    """CRUD + domain queries for the daily_points_log table."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="daily_points_log", id_column="log_id")

    def find_by_user_and_date(self, user_id: str, log_date: str) -> dict[str, Any] | None:
        """Find a daily log entry for a user on a specific date."""
        entries = self.find_by_field("user_id", user_id)
        for entry in entries:
            if str(entry.get("log_date", ""))[:10] == log_date[:10]:
                return entry
        return None

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        """Find all daily log entries for a user."""
        return self.find_by_field("user_id", user_id)
