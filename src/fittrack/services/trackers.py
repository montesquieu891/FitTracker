"""Tracker service — manages OAuth flows and provider connections."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fittrack.services.providers.base import BaseProvider, ProviderError, TokenInfo

logger = logging.getLogger(__name__)


class TrackerError(Exception):
    """Tracker service error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class TrackerService:
    """Manages tracker connections and OAuth flows.

    Coordinates between provider clients and the connection repository.
    """

    def __init__(
        self,
        connection_repo: Any,
        providers: dict[str, BaseProvider] | None = None,
    ) -> None:
        self.connection_repo = connection_repo
        self.providers = providers or {}

    def get_provider(self, provider_name: str) -> BaseProvider:
        """Get a provider client by name."""
        provider = self.providers.get(provider_name)
        if not provider:
            raise TrackerError(f"Unsupported provider: {provider_name}", status_code=400)
        return provider

    # ── OAuth flow ──────────────────────────────────────────────────

    def initiate_oauth(
        self,
        user_id: str,
        provider_name: str,
        redirect_uri: str,
    ) -> dict[str, str]:
        """Start the OAuth flow — return authorization URL and state token."""
        provider = self.get_provider(provider_name)

        # Check for existing connection
        existing = self.connection_repo.find_by_user_id(user_id)
        for conn in existing:
            if conn.get("provider") == provider_name:
                raise TrackerError(
                    f"Already connected to {provider_name}. Disconnect first to reconnect.",
                    status_code=409,
                )

        state = uuid.uuid4().hex
        auth_url = provider.get_authorization_url(state=state, redirect_uri=redirect_uri)

        return {"authorization_url": auth_url, "state": state}

    def complete_oauth(
        self,
        user_id: str,
        provider_name: str,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange auth code for tokens and create the connection record."""
        provider = self.get_provider(provider_name)

        try:
            token_info: TokenInfo = provider.exchange_code(code, redirect_uri)
        except ProviderError as e:
            raise TrackerError(f"OAuth token exchange failed: {e.detail}", status_code=502) from e

        # Determine if this is the user's first connection (make it primary)
        existing = self.connection_repo.find_by_user_id(user_id)
        is_primary = len(existing) == 0

        now = datetime.now(tz=UTC)
        connection_id = uuid.uuid4().hex
        conn_data: dict[str, Any] = {
            "user_id": user_id,
            "provider": provider_name,
            "is_primary": 1 if is_primary else 0,
            "access_token": _encrypt_token(token_info.access_token),
            "refresh_token": _encrypt_token(token_info.refresh_token or ""),
            "token_expires_at": token_info.token_expires_at,
            "sync_status": "connected",
            "created_at": now,
            "updated_at": now,
        }

        self.connection_repo.create(data=conn_data, new_id=connection_id)

        return {
            "connection_id": connection_id,
            "provider": provider_name,
            "is_primary": is_primary,
            "sync_status": "connected",
        }

    def disconnect(self, user_id: str, provider_name: str) -> bool:
        """Disconnect a provider — revoke token and delete connection."""
        connections = self.connection_repo.find_by_user_id(user_id)
        target = None
        for conn in connections:
            if conn.get("provider") == provider_name:
                target = conn
                break

        if not target:
            raise TrackerError(f"No connection found for {provider_name}", status_code=404)

        # Revoke token if provider is available
        provider = self.providers.get(provider_name)
        if provider and target.get("access_token"):
            try:
                token = _decrypt_token(target["access_token"])
                provider.revoke_token(token)
            except ProviderError:
                logger.warning(
                    "Token revocation failed for %s, proceeding",
                    provider_name,
                )

        connection_id = target.get("connection_id", "")
        self.connection_repo.delete(connection_id)
        return True

    def force_sync(self, user_id: str, provider_name: str) -> dict[str, Any]:
        """Mark a connection for immediate sync.

        Returns the connection details. The actual sync is performed
        by the sync worker.
        """
        connections = self.connection_repo.find_by_user_id(user_id)
        target = None
        for conn in connections:
            if conn.get("provider") == provider_name:
                target = conn
                break

        if not target:
            raise TrackerError(f"No connection found for {provider_name}", status_code=404)

        connection_id = target.get("connection_id", "")
        self.connection_repo.update(
            connection_id,
            {"sync_status": "pending", "updated_at": datetime.now(tz=UTC)},
        )

        return {
            "connection_id": connection_id,
            "provider": provider_name,
            "sync_status": "pending",
            "message": "Sync queued",
        }

    def get_user_connections(self, user_id: str) -> list[dict[str, Any]]:
        """Get all connections for a user, stripping sensitive token data."""
        connections = self.connection_repo.find_by_user_id(user_id)
        return [_sanitize_connection(c) for c in connections]

    def refresh_token_if_needed(
        self,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        """Proactively refresh token if it's about to expire.

        Returns updated connection dict.
        """
        expires_at = connection.get("token_expires_at")
        if expires_at is None:
            return connection

        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)

        # Refresh if expires within 5 minutes
        from datetime import timedelta

        if expires_at > datetime.now(tz=UTC) + timedelta(minutes=5):
            return connection  # Still valid

        provider_name = connection.get("provider", "")
        provider = self.providers.get(provider_name)
        if not provider:
            return connection

        refresh_tok = connection.get("refresh_token", "")
        if not refresh_tok:
            return connection

        try:
            decrypted = _decrypt_token(refresh_tok)
            new_tokens = provider.refresh_access_token(decrypted)
            conn_id = connection.get("connection_id", "")
            self.connection_repo.update(
                conn_id,
                {
                    "access_token": _encrypt_token(new_tokens.access_token),
                    "refresh_token": _encrypt_token(new_tokens.refresh_token or decrypted),
                    "token_expires_at": new_tokens.token_expires_at,
                    "updated_at": datetime.now(tz=UTC),
                },
            )
            connection["access_token"] = _encrypt_token(new_tokens.access_token)
            connection["token_expires_at"] = new_tokens.token_expires_at
            logger.info("Refreshed token for connection %s", conn_id)
        except ProviderError as e:
            logger.error("Token refresh failed: %s", e.detail)

        return connection


def _sanitize_connection(conn: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from connection data for API responses."""
    sanitized = dict(conn)
    sanitized.pop("access_token", None)
    sanitized.pop("refresh_token", None)
    return sanitized


def _encrypt_token(token: str) -> str:
    """Encrypt a token for storage.

    MVP: simple base64 encoding. Production would use AES-256-GCM
    with a key from env/KMS.
    """
    import base64

    return base64.urlsafe_b64encode(token.encode()).decode()


def _decrypt_token(encrypted: str) -> str:
    """Decrypt a stored token.

    MVP: simple base64 decoding.
    """
    import base64

    try:
        return base64.urlsafe_b64decode(encrypted.encode()).decode()
    except Exception:
        return encrypted  # Already plaintext
