"""OAuth accounts repository for social login tracking."""

from __future__ import annotations

from fittrack.repositories.base import BaseRepository


class OAuthAccountRepository(BaseRepository):
    """CRUD operations for the oauth_accounts table."""

    def __init__(self, pool: object) -> None:
        super().__init__(
            pool=pool,
            table_name="oauth_accounts",
            id_column="oauth_account_id",
        )
