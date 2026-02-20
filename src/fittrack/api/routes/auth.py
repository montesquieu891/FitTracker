"""Authentication routes — /api/v1/auth."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from fittrack.api.deps import get_current_user, get_current_user_id
from fittrack.api.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from fittrack.services.auth import AuthError, AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _get_auth_service() -> AuthService:
    """Build an AuthService with live repositories."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.session_repository import SessionRepository
    from fittrack.repositories.user_repository import UserRepository

    pool = get_pool()
    return AuthService(
        user_repo=UserRepository(pool=pool),
        session_repo=SessionRepository(pool=pool),
    )


def _handle_auth_error(err: AuthError) -> None:
    """Convert AuthError to HTTPException."""
    raise HTTPException(status_code=err.status_code, detail=err.detail)


# ── Registration ────────────────────────────────────────────────────


@router.post("/register", status_code=201)
def register(body: RegisterRequest) -> dict[str, Any]:
    """Register a new user account."""
    svc = _get_auth_service()
    try:
        result = svc.register(
            email=body.email,
            password=body.password,
            date_of_birth=body.date_of_birth,
            state=body.state,
        )
    except AuthError as e:
        _handle_auth_error(e)
    return result


# ── Login ───────────────────────────────────────────────────────────


@router.post("/login")
def login(body: LoginRequest) -> dict[str, Any]:
    """Login with email and password."""
    svc = _get_auth_service()
    try:
        result = svc.login(email=body.email, password=body.password)
    except AuthError as e:
        _handle_auth_error(e)
    return result


# ── Token Refresh ───────────────────────────────────────────────────


@router.post("/refresh")
def refresh_token(body: RefreshRequest) -> dict[str, Any]:
    """Refresh access token using a refresh token."""
    svc = _get_auth_service()
    try:
        result = svc.refresh_access_token(body.refresh_token)
    except AuthError as e:
        _handle_auth_error(e)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    return result


# ── Email Verification ──────────────────────────────────────────────


@router.post("/verify-email")
def verify_email(body: VerifyEmailRequest) -> dict[str, Any]:
    """Verify email address with token."""
    svc = _get_auth_service()
    try:
        result = svc.verify_email(user_id=body.user_id, token=body.token)
    except AuthError as e:
        _handle_auth_error(e)
    return result


# ── Forgot Password ────────────────────────────────────────────────


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest) -> dict[str, Any]:
    """Initiate password reset flow."""
    svc = _get_auth_service()
    result = svc.forgot_password(email=body.email)
    return result


# ── Reset Password ──────────────────────────────────────────────────


@router.post("/reset-password")
def reset_password(body: ResetPasswordRequest) -> dict[str, Any]:
    """Reset password with new password."""
    svc = _get_auth_service()
    try:
        result = svc.reset_password(
            user_id=body.user_id,
            new_password=body.new_password,
        )
    except AuthError as e:
        _handle_auth_error(e)
    return result


# ── Social Login (Google / Apple) ───────────────────────────────────


@router.post("/social/google")
def social_google() -> dict[str, Any]:
    """Google OAuth login (stub — requires Google API integration)."""
    raise HTTPException(
        status_code=501,
        detail="Google OAuth integration coming in v1.1",
    )


@router.post("/social/apple")
def social_apple() -> dict[str, Any]:
    """Apple Sign-In (stub — requires Apple API integration)."""
    raise HTTPException(
        status_code=501,
        detail="Apple Sign-In integration coming in v1.1",
    )


# ── Logout ──────────────────────────────────────────────────────────


@router.post("/logout")
def logout(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Logout current session."""
    svc = _get_auth_service()
    session_id = current_user.get("sid", "")
    result = svc.logout(session_id=session_id)
    return result


@router.post("/logout-all")
def logout_all(
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Logout all sessions for the current user."""
    svc = _get_auth_service()
    result = svc.logout_all(user_id=user_id)
    return result


# ── Current User ────────────────────────────────────────────────────


@router.get("/me")
def get_me(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get current user profile from JWT."""
    svc = _get_auth_service()
    user_id = current_user.get("sub", "")
    user = svc.user_repo.find_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Remove sensitive fields
    user.pop("password_hash", None)
    user.pop("failed_login_attempts", None)
    user.pop("locked_until", None)
    return user
