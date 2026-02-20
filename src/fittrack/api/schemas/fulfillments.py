"""Prize fulfillment entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FulfillmentUpdate(BaseModel):
    """Schema for updating a fulfillment."""

    status: str | None = Field(
        default=None,
        pattern=r"^(pending|winner_notified|address_confirmed|address_invalid|shipped|delivered|forfeited)$",
    )
    shipping_address: dict[str, Any] | None = None
    tracking_number: str | None = None
    carrier: str | None = None
    notes: str | None = None


class FulfillmentCreate(BaseModel):
    """Schema for creating a fulfillment record."""

    ticket_id: str
    prize_id: str
    user_id: str
    status: str = Field(
        default="pending",
        pattern=r"^(pending|winner_notified|address_confirmed|address_invalid|shipped|delivered|forfeited)$",
    )
    shipping_address: dict[str, Any] | None = None


class FulfillmentResponse(BaseModel):
    """Schema for fulfillment in API responses."""

    fulfillment_id: str
    ticket_id: str
    prize_id: str
    user_id: str
    status: str = "pending"
    shipping_address: Any = None
    tracking_number: str | None = None
    carrier: str | None = None
    notes: str | None = None
    notified_at: datetime | None = None
    address_confirmed_at: datetime | None = None
    shipped_at: datetime | None = None
    delivered_at: datetime | None = None
    forfeit_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
