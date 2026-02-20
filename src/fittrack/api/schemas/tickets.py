"""Ticket entity schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TicketCreate(BaseModel):
    """Schema for creating a ticket."""

    drawing_id: str
    user_id: str
    purchase_transaction_id: str | None = None


class TicketResponse(BaseModel):
    """Schema for ticket in API responses."""

    ticket_id: str
    drawing_id: str
    user_id: str
    ticket_number: int | None = None
    purchase_transaction_id: str | None = None
    is_winner: bool = False
    prize_id: str | None = None
    created_at: datetime | None = None
