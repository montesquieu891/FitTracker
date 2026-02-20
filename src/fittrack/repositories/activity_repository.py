"""Activity repository — data access for the ``activities`` table."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fittrack.repositories.base import BaseRepository


class ActivityRepository(BaseRepository):
    """CRUD + domain queries for activities."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="activities", id_column="activity_id")

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        """Find all activities for a user."""
        return self.find_by_field("user_id", user_id)

    def find_by_user_and_date_range(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Find activities for a user within a date range."""
        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                sql = (
                    f"SELECT * FROM {self.table_name} "
                    "WHERE user_id = :user_id "
                    "AND start_time >= :start_date "
                    "AND start_time < :end_date "
                    "ORDER BY start_time"
                )
                cur.execute(sql, {
                    "user_id": user_id,
                    "start_date": start_date,
                    "end_date": end_date,
                })
                columns = [col[0].lower() for col in (cur.description or [])]
                return [
                    dict(zip(columns, row, strict=True))
                    for row in cur.fetchall()
                ]
        finally:
            conn.close()
