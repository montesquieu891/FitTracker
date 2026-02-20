"""Tests for the AuthService — registration, login, refresh, lockout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from fittrack.services.auth import (
    LOCKOUT_DURATION_MINUTES,
    MAX_FAILED_ATTEMPTS,
    AuthError,
    AuthService,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_user_repo(users: list[dict[str, Any]] | None = None) -> MagicMock:
    """Create a mock user repository."""
    repo = MagicMock()
    repo.find_by_field = MagicMock(return_value=users or [])
    repo.find_by_id = MagicMock(return_value=users[0] if users else None)
    repo.create = MagicMock()
    repo.update = MagicMock(return_value=1)
    return repo


def _make_session_repo() -> MagicMock:
    repo = MagicMock()
    repo.create = MagicMock()
    repo.find_by_id = MagicMock(return_value={"session_id": "s1", "revoked": 0})
    repo.find_by_field = MagicMock(return_value=[])
    repo.update = MagicMock(return_value=1)
    return repo


def _make_hashed_user(
    user_id: str = "uid1",
    email: str = "test@example.com",
    status: str = "active",
    role: str = "user",
    failed_login_attempts: int = 0,
    locked_until: Any = None,
) -> dict[str, Any]:
    """Create a user dict with a real Argon2 hash for 'Str0ng!Pass'."""
    from fittrack.core.security import hash_password

    return {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password("Str0ng!Pass"),
        "email_verified": 1,
        "status": status,
        "role": role,
        "point_balance": 0,
        "points_earned_total": 0,
        "failed_login_attempts": failed_login_attempts,
        "locked_until": locked_until,
        "created_at": datetime.now(tz=UTC),
        "updated_at": datetime.now(tz=UTC),
        "last_login_at": None,
    }


# ── Registration Tests ──────────────────────────────────────────────


class TestRegistration:
    """Registration with full validation."""

    def test_successful_registration(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        result = svc.register(
            email="new@example.com",
            password="Str0ng!Pass",
            date_of_birth="1990-01-15",
            state="TX",
        )

        assert "user_id" in result
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"
        user_repo.create.assert_called_once()

    def test_weak_password_rejected(self) -> None:
        svc = AuthService(user_repo=MagicMock(), session_repo=None)

        with pytest.raises(AuthError, match="uppercase"):
            svc.register(
                email="a@b.com",
                password="weakpass",
                date_of_birth="1990-01-15",
                state="TX",
            )

    def test_underage_rejected(self) -> None:
        svc = AuthService(user_repo=MagicMock(), session_repo=None)

        with pytest.raises(AuthError, match="18 or older"):
            svc.register(
                email="a@b.com",
                password="Str0ng!Pass",
                date_of_birth="2015-06-01",
                state="TX",
            )

    def test_exactly_18_allowed(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        # Calculate date exactly 18 years ago
        today = datetime.now(tz=UTC)
        dob = today.replace(year=today.year - 18)

        result = svc.register(
            email="new@example.com",
            password="Str0ng!Pass",
            date_of_birth=dob.strftime("%Y-%m-%d"),
            state="TX",
        )
        assert "user_id" in result

    def test_excluded_state_ny(self) -> None:
        svc = AuthService(user_repo=MagicMock(), session_repo=None)

        with pytest.raises(AuthError, match="not eligible"):
            svc.register(
                email="a@b.com",
                password="Str0ng!Pass",
                date_of_birth="1990-01-15",
                state="NY",
            )

    def test_excluded_state_fl(self) -> None:
        svc = AuthService(user_repo=MagicMock(), session_repo=None)

        with pytest.raises(AuthError, match="not eligible"):
            svc.register(
                email="a@b.com",
                password="Str0ng!Pass",
                date_of_birth="1990-01-15",
                state="FL",
            )

    def test_excluded_state_ri(self) -> None:
        svc = AuthService(user_repo=MagicMock(), session_repo=None)

        with pytest.raises(AuthError, match="not eligible"):
            svc.register(
                email="a@b.com",
                password="Str0ng!Pass",
                date_of_birth="1990-01-15",
                state="RI",
            )

    def test_duplicate_email(self) -> None:
        existing_user = _make_hashed_user()
        user_repo = _make_user_repo([existing_user])
        svc = AuthService(user_repo=user_repo, session_repo=None)

        with pytest.raises(AuthError, match="already registered"):
            svc.register(
                email="test@example.com",
                password="Str0ng!Pass",
                date_of_birth="1990-01-15",
                state="TX",
            )

    def test_invalid_dob_format(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo, session_repo=None)

        with pytest.raises(AuthError, match="Invalid date of birth"):
            svc.register(
                email="a@b.com",
                password="Str0ng!Pass",
                date_of_birth="01-15-1990",
                state="TX",
            )

    def test_eligible_state_accepted(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        for state in ["CA", "TX", "OH", "WA", "IL"]:
            result = svc.register(
                email=f"{state.lower()}@example.com",
                password="Str0ng!Pass",
                date_of_birth="1990-01-15",
                state=state,
            )
            assert "access_token" in result


# ── Login Tests ──────────────────────────────────────────────────────


class TestLogin:
    """Login with email/password."""

    def test_successful_login(self) -> None:
        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        result = svc.login(email="test@example.com", password="Str0ng!Pass")

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["role"] == "user"

    def test_wrong_email(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="Invalid email or password"):
            svc.login(email="nonexistent@example.com", password="Str0ng!Pass")

    def test_wrong_password(self) -> None:
        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="Invalid email or password"):
            svc.login(email="test@example.com", password="WrongPass1!")

    def test_banned_account(self) -> None:
        user = _make_hashed_user(status="banned")
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="banned"):
            svc.login(email="test@example.com", password="Str0ng!Pass")

    def test_suspended_account(self) -> None:
        user = _make_hashed_user(status="suspended")
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="suspended"):
            svc.login(email="test@example.com", password="Str0ng!Pass")

    def test_login_resets_failed_attempts(self) -> None:
        user = _make_hashed_user(failed_login_attempts=3)
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        svc.login(email="test@example.com", password="Str0ng!Pass")

        # Verify update was called to reset failed_login_attempts
        # update is called as update(user_id, {data})
        update_call = user_repo.update.call_args
        update_data = update_call[0][1]  # second positional arg
        assert update_data["failed_login_attempts"] == 0


# ── Account Lockout Tests ────────────────────────────────────────────


class TestAccountLockout:
    """Account lockout after failed attempts."""

    def test_lockout_after_max_attempts(self) -> None:
        user = _make_hashed_user(failed_login_attempts=MAX_FAILED_ATTEMPTS - 1)
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="Invalid email or password"):
            svc.login(email="test@example.com", password="WrongPass1!")

        # Should have set locked_until
        update_call = user_repo.update.call_args
        update_data = update_call[0][1]  # second positional arg
        assert "locked_until" in update_data

    def test_locked_account_rejected(self) -> None:
        future = datetime.now(tz=UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
        user = _make_hashed_user(locked_until=future)
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="Account locked"):
            svc.login(email="test@example.com", password="Str0ng!Pass")

    def test_expired_lockout_allows_login(self) -> None:
        past = datetime.now(tz=UTC) - timedelta(minutes=1)
        user = _make_hashed_user(locked_until=past)
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        result = svc.login(email="test@example.com", password="Str0ng!Pass")
        assert "access_token" in result

    def test_lockout_duration_is_15_min(self) -> None:
        assert LOCKOUT_DURATION_MINUTES == 15

    def test_max_failed_attempts_is_5(self) -> None:
        assert MAX_FAILED_ATTEMPTS == 5


# ── Token Refresh Tests ──────────────────────────────────────────────


class TestTokenRefresh:
    """Refresh token flow."""

    def test_successful_refresh(self) -> None:
        from fittrack.core.security import create_refresh_token

        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        user_repo.find_by_id = MagicMock(return_value=user)
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        refresh = create_refresh_token(subject="uid1", session_id="sid1")
        result = svc.refresh_access_token(refresh)

        assert "access_token" in result
        assert result["token_type"] == "bearer"

    def test_refresh_with_access_token_rejected(self) -> None:
        from fittrack.core.security import create_access_token

        svc = AuthService(user_repo=MagicMock())

        access = create_access_token(subject="uid1")
        with pytest.raises(AuthError, match="Invalid token type"):
            svc.refresh_access_token(access)

    def test_refresh_revoked_session(self) -> None:
        from fittrack.core.security import create_refresh_token

        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        user_repo.find_by_id = MagicMock(return_value=user)
        session_repo = _make_session_repo()
        session_repo.find_by_id = MagicMock(return_value={"session_id": "s1", "revoked": 1})

        svc = AuthService(user_repo=user_repo, session_repo=session_repo)

        refresh = create_refresh_token(subject="uid1", session_id="s1")
        with pytest.raises(AuthError, match="Session revoked"):
            svc.refresh_access_token(refresh)


# ── Email Verification Tests ────────────────────────────────────────


class TestEmailVerification:
    """Email verification flow."""

    def test_verify_email_success(self) -> None:
        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        user_repo.find_by_id = MagicMock(return_value=user)
        svc = AuthService(user_repo=user_repo)

        result = svc.verify_email(user_id="uid1", token="tok123")
        assert result["message"] == "Email verified successfully"
        user_repo.update.assert_called_once()

    def test_verify_nonexistent_user(self) -> None:
        user_repo = MagicMock()
        user_repo.find_by_id = MagicMock(return_value=None)
        svc = AuthService(user_repo=user_repo)

        with pytest.raises(AuthError, match="User not found"):
            svc.verify_email(user_id="bad", token="tok")


# ── Logout Tests ─────────────────────────────────────────────────────


class TestLogout:
    """Logout and logout-all flows."""

    def test_logout_single_session(self) -> None:
        session_repo = _make_session_repo()
        svc = AuthService(user_repo=MagicMock(), session_repo=session_repo)

        result = svc.logout(session_id="s1")
        assert result["message"] == "Logged out successfully"
        session_repo.update.assert_called_once()

    def test_logout_all_sessions(self) -> None:
        session_repo = _make_session_repo()
        session_repo.find_by_field = MagicMock(
            return_value=[
                {"session_id": "s1", "revoked": 0},
                {"session_id": "s2", "revoked": 0},
            ]
        )
        svc = AuthService(user_repo=MagicMock(), session_repo=session_repo)

        result = svc.logout_all(user_id="uid1")
        assert result["message"] == "All sessions revoked"
        assert session_repo.update.call_count == 2


# ── Forgot / Reset Password Tests ───────────────────────────────────


class TestPasswordReset:
    """Password reset flow."""

    def test_forgot_password_existing_email(self) -> None:
        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        svc = AuthService(user_repo=user_repo)

        result = svc.forgot_password(email="test@example.com")
        assert "reset_token" in result
        assert result["message"] == "If the email exists, a reset link has been sent"

    def test_forgot_password_nonexistent_email(self) -> None:
        user_repo = _make_user_repo([])
        svc = AuthService(user_repo=user_repo)

        result = svc.forgot_password(email="none@example.com")
        # Always returns success to prevent email enumeration
        assert "reset_token" in result

    def test_reset_password_success(self) -> None:
        user = _make_hashed_user()
        user_repo = _make_user_repo([user])
        user_repo.find_by_id = MagicMock(return_value=user)
        svc = AuthService(user_repo=user_repo, session_repo=_make_session_repo())

        result = svc.reset_password(user_id="uid1", new_password="N3w!Passw0rd")
        assert result["message"] == "Password reset successfully"

    def test_reset_password_weak(self) -> None:
        svc = AuthService(user_repo=MagicMock())

        with pytest.raises(AuthError):
            svc.reset_password(user_id="uid1", new_password="weak")
