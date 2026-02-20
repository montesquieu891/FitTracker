"""Authentication request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    date_of_birth: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date of birth in YYYY-MM-DD format (must be 18+)",
    )
    state: str = Field(
        min_length=2,
        max_length=2,
        description="US state abbreviation (NY, FL, RI excluded)",
    )


class LoginRequest(BaseModel):
    """Email/password login request."""

    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class VerifyEmailRequest(BaseModel):
    """Email verification request."""

    user_id: str
    token: str


class ForgotPasswordRequest(BaseModel):
    """Forgot password request."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password request."""

    user_id: str
    new_password: str = Field(min_length=8, max_length=128)


class SocialLoginRequest(BaseModel):
    """Social login (Google / Apple) request."""

    provider: str = Field(pattern=r"^(google|apple)$")
    id_token: str


class AuthResponse(BaseModel):
    """Authentication response with tokens."""

    user_id: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    role: str = "user"


class TokenResponse(BaseModel):
    """Refreshed token response."""

    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
