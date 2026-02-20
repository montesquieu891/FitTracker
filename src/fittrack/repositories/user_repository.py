"""User repository — data access for the ``users`` table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fittrack.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    """CRUD + domain queries for users."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="users", id_column="user_id")

    def find_by_email(self, email: str) -> dict[str, Any] | None:
        """Find a user by email address."""
        results = self.find_by_field("email", email)
        return results[0] if results else None

    def update_point_balance(self, user_id: str, new_balance: int) -> int:
        """Update a user's spendable point balance."""
        return self.update(user_id, data={"point_balance": new_balance})

    def update_last_login(self, user_id: str) -> int:
        """Set last_login_at to now."""
        now = datetime.now(UTC).isoformat()
        return self.update(user_id, data={"last_login_at": now})
