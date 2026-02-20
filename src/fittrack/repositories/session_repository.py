"""Session repository for refresh-token tracking."""

from __future__ import annotations

from fittrack.repositories.base import BaseRepository


class SessionRepository(BaseRepository):
    """CRUD operations for the sessions table."""

    def __init__(self, pool: object) -> None:
        super().__init__(pool=pool, table_name="sessions", id_column="session_id")
