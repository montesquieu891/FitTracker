"""Sponsor repository — data access for the ``sponsors`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class SponsorRepository(BaseRepository):
    """CRUD + domain queries for sponsors."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="sponsors", id_column="sponsor_id")

    def find_active(self) -> list[dict[str, Any]]:
        """Find all active sponsors."""
        return self.find_by_field("status", "active")
