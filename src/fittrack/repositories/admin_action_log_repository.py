"""Admin actions log repository — data access for ``admin_actions_log`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class AdminActionLogRepository(BaseRepository):
    def __init__(self, pool: Any) -> None:
        super().__init__(
            pool=pool,
            table_name="admin_actions_log",
            id_column="log_id",
        )

    def find_by_admin(self, admin_user_id: str) -> list[dict[str, Any]]:
        return self.find_by_field("admin_user_id", admin_user_id)

    def find_by_target(self, target_user_id: str) -> list[dict[str, Any]]:
        return self.find_by_field("target_user_id", target_user_id)
