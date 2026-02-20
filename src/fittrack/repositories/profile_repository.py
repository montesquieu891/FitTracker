"""Profile repository — data access for the ``profiles`` table."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class ProfileRepository(BaseRepository):
    """CRUD + domain queries for profiles."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="profiles", id_column="profile_id")

    def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        """Find the profile belonging to a user."""
        results = self.find_by_field("user_id", user_id)
        return results[0] if results else None

    def find_by_tier_code(self, tier_code: str) -> list[dict[str, Any]]:
        """Find all profiles in a given competition tier."""
        return self.find_by_field("tier_code", tier_code)
