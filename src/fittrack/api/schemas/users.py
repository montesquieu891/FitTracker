"""User entity schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    """Schema for creating a user."""

    email: EmailStr
    password_hash: str = Field(
        min_length=1,
        description="Pre-hashed password (CP2 will handle hashing)",
    )
    role: str = Field(default="user", pattern=r"^(user|premium|admin)$")
    status: str = Field(default="pending", pattern=r"^(pending|active|suspended|banned)$")


class UserUpdate(BaseModel):
    """Schema for updating a user."""

    email: EmailStr | None = None
    status: str | None = Field(default=None, pattern=r"^(pending|active|suspended|banned)$")
    role: str | None = Field(default=None, pattern=r"^(user|premium|admin)$")
    point_balance: int | None = Field(default=None, ge=0)
    email_verified: bool | None = None


class UserResponse(BaseModel):
    """Schema for user in API responses."""

    user_id: str
    email: str
    email_verified: bool = False
    status: str = "pending"
    role: str = "user"
    point_balance: int = 0
    created_at: datetime | None = None
    updated_at: datetime | None = None
    last_login_at: datetime | None = None


class UserListResponse(BaseModel):
    """Paginated list of users."""

    items: list[UserResponse]
    pagination: dict[str, int]
