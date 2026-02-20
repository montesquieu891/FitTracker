"""Point transaction schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TransactionCreate(BaseModel):
    """Schema for creating a point transaction."""

    user_id: str
    transaction_type: str = Field(pattern=r"^(earn|spend|adjust)$")
    amount: int
    balance_after: int = Field(ge=0)
    reference_type: str | None = None
    reference_id: str | None = None
    description: str | None = None


class TransactionResponse(BaseModel):
    """Schema for transaction in API responses."""

    transaction_id: str
    user_id: str
    transaction_type: str
    amount: int
    balance_after: int
    reference_type: str | None = None
    reference_id: str | None = None
    description: str | None = None
    created_at: datetime | None = None
