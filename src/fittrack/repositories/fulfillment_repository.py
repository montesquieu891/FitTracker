"""Fulfillment repository — data access for ``prize_fulfillments``."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class FulfillmentRepository(BaseRepository):
    """CRUD + domain queries for prize fulfillments."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="prize_fulfillments", id_column="fulfillment_id")

    def find_by_user(self, user_id: str) -> list[dict[str, Any]]:
        """Find all fulfillments for a user."""
        return self.find_by_field("user_id", user_id)

    def find_pending(self) -> list[dict[str, Any]]:
        """Find all fulfillments with status 'pending'."""
        return self.find_by_field("status", "pending")
