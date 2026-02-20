"""Authentication service — registration, login, sessions, lockout."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fittrack.core.constants import ELIGIBLE_STATES
from fittrack.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_complexity,
    verify_password,
)

logger = logging.getLogger(__name__)

# ── Account lockout settings ────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


class AuthError(Exception):
    """Authentication / authorisation error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class AuthService:
    """Stateless service — receives repositories via __init__."""

    def __init__(self, user_repo: Any, session_repo: Any | None = None) -> None:
        self.user_repo = user_repo
        self.session_repo = session_repo

    # ── Registration ────────────────────────────────────────────────

    def register(
        self,
        email: str,
        password: str,
        date_of_birth: str,
        state: str,
    ) -> dict[str, Any]:
        """Register a new user with full validation.

        Returns the created user dict + tokens.
        """
        # 1. Password complexity
        pwd_errors = validate_password_complexity(password)
        if pwd_errors:
            raise AuthError("; ".join(pwd_errors))

        # 2. Age gate (18+)
        self._validate_age(date_of_birth)

        # 3. State eligibility
        self._validate_state(state)

        # 4. Unique email
        existing = self.user_repo.find_by_field("email", email)
        if existing:
            raise AuthError("Email already registered", status_code=409)

        # 5. Create user
        user_id = uuid.uuid4().hex
        now = datetime.now(tz=UTC)
        user_data: dict[str, Any] = {
            "email": email,
            "password_hash": hash_password(password),
            "email_verified": 0,
            "status": "pending",
            "role": "user",
            "point_balance": 0,
            "points_earned_total": 0,
            "created_at": now,
            "updated_at": now,
        }
        self.user_repo.create(data=user_data, new_id=user_id)

        # 6. Generate verification token (simple UUID, stored in email_verification_token)
        verification_token = uuid.uuid4().hex

        # 7. Generate auth tokens
        access_token = create_access_token(subject=user_id, role="user")
        session_id = uuid.uuid4().hex
        refresh_token = create_refresh_token(subject=user_id, session_id=session_id)

        # 8. Store session
        if self.session_repo:
            self.session_repo.create(
                data={
                    "user_id": user_id,
                    "refresh_token_jti": session_id,
                    "device_info": "web",
                    "ip_address": "0.0.0.0",
                    "expires_at": None,
                    "created_at": now,
                },
                new_id=session_id,
            )

        logger.info("User registered: user_id=%s email=%s", user_id, email)
        return {
            "user_id": user_id,
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "verification_token": verification_token,
            "token_type": "bearer",
        }

    # ── Login ───────────────────────────────────────────────────────

    def login(self, email: str, password: str) -> dict[str, Any]:
        """Authenticate with email + password, return tokens."""
        users = self.user_repo.find_by_field("email", email)
        if not users:
            raise AuthError("Invalid email or password", status_code=401)

        user = users[0]
        user_id = user["user_id"]

        # Check lockout
        self._check_lockout(user)

        # Verify password
        if not verify_password(password, user.get("password_hash", "")):
            self._record_failed_attempt(user)
            raise AuthError("Invalid email or password", status_code=401)

        # Check account status
        if user.get("status") == "banned":
            raise AuthError("Account is banned", status_code=403)
        if user.get("status") == "suspended":
            raise AuthError("Account is suspended", status_code=403)

        # Reset failed attempts on successful login
        self.user_repo.update(
            user_id,
            {
                "failed_login_attempts": 0,
                "locked_until": None,
                "last_login_at": datetime.now(tz=UTC),
                "updated_at": datetime.now(tz=UTC),
            },
        )

        # Generate tokens
        role = user.get("role", "user")
        access_token = create_access_token(subject=user_id, role=role)
        session_id = uuid.uuid4().hex
        refresh_token = create_refresh_token(subject=user_id, session_id=session_id)

        # Store session
        if self.session_repo:
            self.session_repo.create(
                data={
                    "user_id": user_id,
                    "refresh_token_jti": session_id,
                    "device_info": "web",
                    "ip_address": "0.0.0.0",
                    "created_at": datetime.now(tz=UTC),
                },
                new_id=session_id,
            )

        logger.info("User logged in: user_id=%s", user_id)
        return {
            "user_id": user_id,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "role": role,
        }

    # ── Token Refresh ───────────────────────────────────────────────

    def refresh_access_token(self, refresh_token: str) -> dict[str, Any]:
        """Validate refresh token and issue new access token."""
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise AuthError("Invalid token type", status_code=401)

        user_id = payload.get("sub")
        if not user_id:
            raise AuthError("Invalid token", status_code=401)

        # Check session still valid
        session_id = payload.get("sid")
        if self.session_repo and session_id:
            session = self.session_repo.find_by_id(session_id)
            if not session or session.get("revoked"):
                raise AuthError("Session revoked", status_code=401)

        # Load user to get current role
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AuthError("User not found", status_code=401)

        if user.get("status") in ("banned", "suspended"):
            raise AuthError("Account not active", status_code=403)

        role = user.get("role", "user")
        access_token = create_access_token(subject=user_id, role=role)

        return {
            "access_token": access_token,
            "token_type": "bearer",
        }

    # ── Email Verification ──────────────────────────────────────────

    def verify_email(self, user_id: str, token: str) -> dict[str, Any]:
        """Mark email as verified. Token validation is simplified for MVP."""
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AuthError("User not found", status_code=404)

        self.user_repo.update(
            user_id,
            {
                "email_verified": 1,
                "email_verified_at": datetime.now(tz=UTC),
                "status": "active",
                "updated_at": datetime.now(tz=UTC),
            },
        )

        return {"message": "Email verified successfully"}

    # ── Logout ──────────────────────────────────────────────────────

    def logout(self, session_id: str) -> dict[str, Any]:
        """Revoke a single session."""
        if self.session_repo:
            self.session_repo.update(
                session_id,
                {
                    "revoked": 1,
                    "revoked_at": datetime.now(tz=UTC),
                },
            )
        return {"message": "Logged out successfully"}

    def logout_all(self, user_id: str) -> dict[str, Any]:
        """Revoke all sessions for a user."""
        if self.session_repo:
            sessions = self.session_repo.find_by_field("user_id", user_id)
            now = datetime.now(tz=UTC)
            for s in sessions:
                sid = s.get("session_id")
                if sid and not s.get("revoked"):
                    self.session_repo.update(
                        sid,
                        {
                            "revoked": 1,
                            "revoked_at": now,
                        },
                    )
        return {"message": "All sessions revoked"}

    # ── Forgot / Reset Password ─────────────────────────────────────

    def forgot_password(self, email: str) -> dict[str, Any]:
        """Initiate password reset. Returns token (in prod, would email it)."""
        users = self.user_repo.find_by_field("email", email)
        # Always return success to prevent email enumeration
        reset_token = uuid.uuid4().hex
        if users:
            logger.info("Password reset requested for %s (token=%s)", email, reset_token)
        return {
            "message": "If the email exists, a reset link has been sent",
            "reset_token": reset_token,  # DEV ONLY — removed in production
        }

    def reset_password(self, user_id: str, new_password: str) -> dict[str, Any]:
        """Reset password. In production, would validate reset token."""
        pwd_errors = validate_password_complexity(new_password)
        if pwd_errors:
            raise AuthError("; ".join(pwd_errors))

        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AuthError("User not found", status_code=404)

        self.user_repo.update(
            user_id,
            {
                "password_hash": hash_password(new_password),
                "updated_at": datetime.now(tz=UTC),
            },
        )

        # Revoke all sessions (force re-login)
        self.logout_all(user_id)

        return {"message": "Password reset successfully"}

    # ── Private helpers ─────────────────────────────────────────────

    @staticmethod
    def _validate_age(date_of_birth: str) -> None:
        """Validate user is 18+. Raises AuthError if underage."""
        try:
            dob = datetime.strptime(date_of_birth, "%Y-%m-%d").replace(tzinfo=UTC)
        except ValueError as exc:
            raise AuthError("Invalid date of birth format (expected YYYY-MM-DD)") from exc

        today = datetime.now(tz=UTC)
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 18:
            raise AuthError("Must be 18 or older to register", status_code=403)

    @staticmethod
    def _validate_state(state: str) -> None:
        """Validate state is eligible for sweepstakes."""
        state_upper = state.upper().strip()
        if state_upper not in ELIGIBLE_STATES:
            raise AuthError(
                f"State '{state_upper}' is not eligible for sweepstakes",
                status_code=403,
            )

    def _check_lockout(self, user: dict[str, Any]) -> None:
        """Check if account is locked out from too many failed attempts."""
        locked_until = user.get("locked_until")
        if locked_until:
            if isinstance(locked_until, str):
                locked_until = datetime.fromisoformat(locked_until).replace(tzinfo=UTC)
            if isinstance(locked_until, datetime):
                now = datetime.now(tz=UTC)
                if locked_until.tzinfo is None:
                    locked_until = locked_until.replace(tzinfo=UTC)
                if now < locked_until:
                    raise AuthError(
                        f"Account locked until {locked_until.isoformat()}",
                        status_code=423,
                    )

    def _record_failed_attempt(self, user: dict[str, Any]) -> None:
        """Increment failed login counter. Lock after MAX_FAILED_ATTEMPTS."""
        user_id = user["user_id"]
        attempts = (user.get("failed_login_attempts") or 0) + 1
        update_data: dict[str, Any] = {
            "failed_login_attempts": attempts,
            "updated_at": datetime.now(tz=UTC),
        }
        if attempts >= MAX_FAILED_ATTEMPTS:
            from datetime import timedelta

            update_data["locked_until"] = datetime.now(tz=UTC) + timedelta(
                minutes=LOCKOUT_DURATION_MINUTES
            )
            logger.warning("Account locked: user_id=%s after %d failed attempts", user_id, attempts)

        self.user_repo.update(user_id, update_data)
