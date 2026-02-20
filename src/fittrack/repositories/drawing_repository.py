"""Drawing repository — data access for the ``drawings`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class DrawingRepository(BaseRepository):
    """CRUD + domain queries for drawings."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="drawings", id_column="drawing_id")

    def find_active(self) -> list[dict[str, Any]]:
        """Find all drawings with status 'open'."""
        return self.find_by_field("status", "open")

    def find_by_type(self, drawing_type: str) -> list[dict[str, Any]]:
        """Find all drawings of a specific type."""
        return self.find_by_field("drawing_type", drawing_type)
