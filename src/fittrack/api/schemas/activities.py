"""Activity entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ActivityCreate(BaseModel):
    """Schema for creating an activity."""

    user_id: str
    connection_id: str | None = None
    external_id: str | None = None
    activity_type: str = Field(pattern=r"^(steps|workout|active_minutes)$")
    start_time: datetime
    end_time: datetime | None = None
    duration_minutes: int | None = Field(default=None, ge=0)
    intensity: str | None = Field(default=None, pattern=r"^(light|moderate|vigorous)$")
    metrics: dict[str, Any] | None = None
    points_earned: int = Field(default=0, ge=0)


class ActivityResponse(BaseModel):
    """Schema for activity in API responses."""

    activity_id: str
    user_id: str
    connection_id: str | None = None
    external_id: str | None = None
    activity_type: str
    start_time: datetime | None = None
    end_time: datetime | None = None
    duration_minutes: int | None = None
    intensity: str | None = None
    metrics: Any = None
    points_earned: int = 0
    processed: bool = False
    created_at: datetime | None = None
