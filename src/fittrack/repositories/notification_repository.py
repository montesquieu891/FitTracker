"""Notification repository — data access for ``notifications`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, pool: Any) -> None:
        super().__init__(
            pool=pool,
            table_name="notifications",
            id_column="notification_id",
        )

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        return self.find_by_field("user_id", user_id)

    def count_unread(self, user_id: str) -> int:
        return self.count(filters={"user_id": user_id, "is_read": 0})
