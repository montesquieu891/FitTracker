"""Prize entity schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PrizeCreate(BaseModel):
    """Schema for creating a prize."""

    drawing_id: str
    sponsor_id: str | None = None
    rank: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    value_usd: float | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, ge=1)
    fulfillment_type: str = Field(default="digital", pattern=r"^(digital|physical)$")
    image_url: str | None = None


class PrizeResponse(BaseModel):
    """Schema for prize in API responses."""

    prize_id: str
    drawing_id: str
    sponsor_id: str | None = None
    rank: int
    name: str
    description: str | None = None
    value_usd: float | None = None
    quantity: int = 1
    fulfillment_type: str = "digital"
    image_url: str | None = None
    created_at: datetime | None = None
