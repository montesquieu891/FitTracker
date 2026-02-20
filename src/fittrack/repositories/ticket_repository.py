"""Ticket repository — data access for the ``tickets`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class TicketRepository(BaseRepository):
    """CRUD + domain queries for tickets."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="tickets", id_column="ticket_id")

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        """Find all tickets for a drawing."""
        return self.find_by_field("drawing_id", drawing_id)

    def find_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Find all tickets for a user."""
        return self.find_by_field("user_id", user_id)

    def count_by_drawing(self, drawing_id: str) -> int:
        """Count tickets sold for a specific drawing."""
        return self.count(filters={"drawing_id": drawing_id})
