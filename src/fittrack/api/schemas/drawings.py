"""Drawing entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DrawingCreate(BaseModel):
    """Schema for creating a drawing."""

    drawing_type: str = Field(pattern=r"^(daily|weekly|monthly|annual)$")
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    ticket_cost_points: int = Field(ge=1)
    drawing_time: datetime
    ticket_sales_close: datetime
    eligibility: dict[str, Any] | None = None
    status: str = Field(
        default="draft",
        pattern=r"^(draft|scheduled|open|closed|completed|cancelled)$",
    )
    created_by: str | None = None


class DrawingUpdate(BaseModel):
    """Schema for updating a drawing."""

    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    ticket_cost_points: int | None = Field(default=None, ge=1)
    drawing_time: datetime | None = None
    ticket_sales_close: datetime | None = None
    eligibility: dict[str, Any] | None = None
    status: str | None = Field(
        default=None, pattern=r"^(draft|scheduled|open|closed|completed|cancelled)$"
    )


class DrawingResponse(BaseModel):
    """Schema for drawing in API responses."""

    drawing_id: str
    drawing_type: str
    name: str
    description: str | None = None
    ticket_cost_points: int
    drawing_time: datetime | None = None
    ticket_sales_close: datetime | None = None
    eligibility: Any = None
    status: str = "draft"
    total_tickets: int = 0
    random_seed: str | None = None
    created_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    completed_at: datetime | None = None
