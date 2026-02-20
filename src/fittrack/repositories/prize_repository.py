"""Prize repository — data access for the ``prizes`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class PrizeRepository(BaseRepository):
    """CRUD + domain queries for prizes."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="prizes", id_column="prize_id")

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        """Find all prizes for a drawing, ordered by rank."""
        return self.find_by_field("drawing_id", drawing_id)
