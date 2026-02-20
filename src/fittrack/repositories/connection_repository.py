"""Tracker connection repository — data access for ``tracker_connections``."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class ConnectionRepository(BaseRepository):
    """CRUD + domain queries for tracker connections."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="tracker_connections", id_column="connection_id")

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        """Find all tracker connections for a user."""
        return self.find_by_field("user_id", user_id)
