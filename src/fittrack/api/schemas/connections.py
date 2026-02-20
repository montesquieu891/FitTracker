"""Tracker connection schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ConnectionCreate(BaseModel):
    """Schema for creating a tracker connection."""

    user_id: str
    provider: str = Field(pattern=r"^(google_fit|fitbit)$")
    is_primary: bool = False
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


class ConnectionResponse(BaseModel):
    """Schema for connection in API responses."""

    connection_id: str
    user_id: str
    provider: str
    is_primary: bool = False
    last_sync_at: datetime | None = None
    sync_status: str = "pending"
    error_message: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
