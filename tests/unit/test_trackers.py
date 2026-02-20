"""Tests for tracker service — OAuth flow management."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fittrack.services.providers.base import ProviderError, TokenInfo
from fittrack.services.trackers import (
    TrackerError,
    TrackerService,
    _decrypt_token,
    _encrypt_token,
    _sanitize_connection,
)

# ── Helpers ──────────────────────────────────────────────────────────


class MockConnectionRepo:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._items: list[dict[str, Any]] = items or []
        self._created: list[dict[str, Any]] = []
        self._updates: list[tuple[str, dict[str, Any]]] = []
        self._deletions: list[str] = []

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        return [i for i in self._items if i.get("user_id") == user_id]

    def create(self, data: dict[str, Any], new_id: str = "") -> dict[str, Any]:
        data["connection_id"] = new_id
        self._created.append(data)
        self._items.append(data)
        return data

    def update(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._updates.append((item_id, data))
        return data

    def delete(self, item_id: str) -> bool:
        self._deletions.append(item_id)
        self._items = [i for i in self._items if i.get("connection_id") != item_id]
        return True


class MockProvider:
    def __init__(self, provider_name: str = "google_fit") -> None:
        self.provider_name = provider_name
        self._exchange_result = TokenInfo(
            access_token="access_tok",
            refresh_token="refresh_tok",
            token_expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )
        self._revoked: list[str] = []
        self._exchange_fails = False

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        return f"https://auth.example.com?state={state}&redirect_uri={redirect_uri}"

    def exchange_code(self, code: str, redirect_uri: str) -> TokenInfo:
        if self._exchange_fails:
            raise ProviderError(self.provider_name, "Exchange failed")
        return self._exchange_result

    def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        return TokenInfo(
            access_token="refreshed_access",
            refresh_token=refresh_token,
            token_expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
        )

    def revoke_token(self, token: str) -> bool:
        self._revoked.append(token)
        return True


def _make_connection(
    user_id: str = "user1",
    provider: str = "google_fit",
    connection_id: str = "conn1",
) -> dict[str, Any]:
    return {
        "connection_id": connection_id,
        "user_id": user_id,
        "provider": provider,
        "access_token": _encrypt_token("my_access_token"),
        "refresh_token": _encrypt_token("my_refresh_token"),
        "sync_status": "connected",
        "is_primary": 1,
    }


# ── Token encryption ────────────────────────────────────────────────


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        original = "secret_token_12345"
        encrypted = _encrypt_token(original)
        assert encrypted != original
        assert _decrypt_token(encrypted) == original

    def test_encrypt_produces_base64(self):
        encrypted = _encrypt_token("test")
        # Should be valid base64
        decoded = base64.urlsafe_b64decode(encrypted)
        assert decoded == b"test"

    def test_decrypt_plaintext_fallback(self):
        """Plaintext that's not valid base64 returns as-is."""
        result = _decrypt_token("not_base64!!!")
        # Should not crash, returns something
        assert isinstance(result, str)

    def test_empty_token(self):
        enc = _encrypt_token("")
        assert _decrypt_token(enc) == ""


# ── _sanitize_connection ────────────────────────────────────────────


class TestSanitizeConnection:
    def test_removes_tokens(self):
        conn = {
            "connection_id": "c1",
            "provider": "google_fit",
            "access_token": "secret",
            "refresh_token": "secret2",
            "sync_status": "connected",
        }
        sanitized = _sanitize_connection(conn)
        assert "access_token" not in sanitized
        assert "refresh_token" not in sanitized
        assert sanitized["provider"] == "google_fit"

    def test_original_unchanged(self):
        conn = {"access_token": "secret", "provider": "test"}
        _sanitize_connection(conn)
        assert "access_token" in conn


# ── TrackerService.get_provider ────────────────────────────────────


class TestGetProvider:
    def test_returns_provider(self):
        provider = MockProvider()
        service = TrackerService(MockConnectionRepo(), {"google_fit": provider})
        assert service.get_provider("google_fit") is provider

    def test_raises_on_unknown(self):
        service = TrackerService(MockConnectionRepo(), {})
        with pytest.raises(TrackerError, match="Unsupported"):
            service.get_provider("unknown")


# ── TrackerService.initiate_oauth ──────────────────────────────────


class TestInitiateOAuth:
    def test_returns_auth_url_and_state(self):
        provider = MockProvider()
        service = TrackerService(MockConnectionRepo(), {"google_fit": provider})
        result = service.initiate_oauth("user1", "google_fit", "http://localhost/cb")
        assert "authorization_url" in result
        assert "state" in result
        assert "auth.example.com" in result["authorization_url"]

    def test_rejects_if_already_connected(self):
        conn = _make_connection(user_id="user1", provider="google_fit")
        repo = MockConnectionRepo([conn])
        provider = MockProvider()
        service = TrackerService(repo, {"google_fit": provider})
        with pytest.raises(TrackerError, match="Already connected"):
            service.initiate_oauth("user1", "google_fit", "http://localhost/cb")

    def test_allows_different_provider(self):
        conn = _make_connection(user_id="user1", provider="google_fit")
        repo = MockConnectionRepo([conn])
        fb = MockProvider("fitbit")
        service = TrackerService(repo, {"fitbit": fb})
        result = service.initiate_oauth("user1", "fitbit", "http://localhost/cb")
        assert "authorization_url" in result


# ── TrackerService.complete_oauth ──────────────────────────────────


class TestCompleteOAuth:
    def test_creates_connection(self):
        repo = MockConnectionRepo()
        provider = MockProvider()
        service = TrackerService(repo, {"google_fit": provider})
        result = service.complete_oauth("user1", "google_fit", "code123", "http://cb")
        assert result["provider"] == "google_fit"
        assert result["is_primary"] is True
        assert len(repo._created) == 1

    def test_first_connection_is_primary(self):
        repo = MockConnectionRepo()
        provider = MockProvider()
        service = TrackerService(repo, {"google_fit": provider})
        result = service.complete_oauth("user1", "google_fit", "code", "http://cb")
        assert result["is_primary"] is True

    def test_second_connection_not_primary(self):
        existing = _make_connection(user_id="user1", provider="google_fit")
        repo = MockConnectionRepo([existing])
        fb = MockProvider("fitbit")
        service = TrackerService(repo, {"fitbit": fb})
        result = service.complete_oauth("user1", "fitbit", "code", "http://cb")
        assert result["is_primary"] is False

    def test_exchange_failure_raises_tracker_error(self):
        repo = MockConnectionRepo()
        provider = MockProvider()
        provider._exchange_fails = True
        service = TrackerService(repo, {"google_fit": provider})
        with pytest.raises(TrackerError, match="exchange failed"):
            service.complete_oauth("user1", "google_fit", "code", "http://cb")


# ── TrackerService.disconnect ──────────────────────────────────────


class TestDisconnect:
    def test_disconnects_and_revokes(self):
        conn = _make_connection()
        repo = MockConnectionRepo([conn])
        provider = MockProvider()
        service = TrackerService(repo, {"google_fit": provider})
        result = service.disconnect("user1", "google_fit")
        assert result is True
        assert len(provider._revoked) == 1
        assert len(repo._deletions) == 1

    def test_disconnect_not_found_raises(self):
        repo = MockConnectionRepo()
        service = TrackerService(repo, {"google_fit": MockProvider()})
        with pytest.raises(TrackerError, match="No connection found"):
            service.disconnect("user1", "google_fit")


# ── TrackerService.force_sync ──────────────────────────────────────


class TestForceSync:
    def test_marks_pending(self):
        conn = _make_connection()
        repo = MockConnectionRepo([conn])
        service = TrackerService(repo, {"google_fit": MockProvider()})
        result = service.force_sync("user1", "google_fit")
        assert result["sync_status"] == "pending"
        assert len(repo._updates) == 1
        assert repo._updates[0][1]["sync_status"] == "pending"

    def test_force_sync_not_found(self):
        service = TrackerService(MockConnectionRepo(), {"google_fit": MockProvider()})
        with pytest.raises(TrackerError, match="No connection found"):
            service.force_sync("user1", "google_fit")


# ── TrackerService.get_user_connections ────────────────────────────


class TestGetUserConnections:
    def test_returns_sanitized(self):
        conn = _make_connection()
        repo = MockConnectionRepo([conn])
        service = TrackerService(repo, {})
        connections = service.get_user_connections("user1")
        assert len(connections) == 1
        assert "access_token" not in connections[0]
        assert "refresh_token" not in connections[0]


# ── TrackerService.refresh_token_if_needed ─────────────────────────


class TestRefreshTokenIfNeeded:
    def test_no_refresh_when_valid(self):
        conn = _make_connection()
        conn["token_expires_at"] = datetime.now(tz=UTC) + timedelta(hours=1)
        service = TrackerService(MockConnectionRepo([conn]), {"google_fit": MockProvider()})
        result = service.refresh_token_if_needed(conn)
        assert result is conn  # Not modified

    def test_refresh_when_expiring_soon(self):
        conn = _make_connection()
        conn["token_expires_at"] = datetime.now(tz=UTC) + timedelta(minutes=2)
        repo = MockConnectionRepo([conn])
        provider = MockProvider()
        service = TrackerService(repo, {"google_fit": provider})
        service.refresh_token_if_needed(conn)
        assert len(repo._updates) == 1

    def test_no_refresh_when_no_expires_at(self):
        conn = _make_connection()
        conn.pop("token_expires_at", None)
        service = TrackerService(MockConnectionRepo([conn]), {"google_fit": MockProvider()})
        result = service.refresh_token_if_needed(conn)
        assert result is conn
