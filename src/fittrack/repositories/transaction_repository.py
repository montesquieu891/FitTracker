"""Point transaction repository — data access for ``point_transactions``."""

from __future__ import annotations

from typing import Any

from fittrack.repositories.base import BaseRepository


class TransactionRepository(BaseRepository):
    """CRUD + domain queries for point transactions."""

    def __init__(self, pool: Any) -> None:
        super().__init__(pool=pool, table_name="point_transactions", id_column="transaction_id")

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        """Find all transactions for a user."""
        return self.find_by_field("user_id", user_id)

    def get_user_balance(self, user_id: str) -> int:
        """Get the current point balance for a user from the users table."""
        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                sql = "SELECT point_balance FROM users WHERE user_id = :user_id"
                cur.execute(sql, {"user_id": user_id})
                row = cur.fetchone()
                return int(row[0]) if row else 0
        finally:
            conn.close()
