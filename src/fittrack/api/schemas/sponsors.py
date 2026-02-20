"""Sponsor entity schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class SponsorCreate(BaseModel):
    """Schema for creating a sponsor."""

    name: str = Field(min_length=1, max_length=255)
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    status: str = Field(default="active", pattern=r"^(active|inactive)$")
    notes: str | None = None


class SponsorUpdate(BaseModel):
    """Schema for updating a sponsor."""

    name: str | None = Field(default=None, max_length=255)
    contact_name: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    status: str | None = Field(default=None, pattern=r"^(active|inactive)$")
    notes: str | None = None


class SponsorResponse(BaseModel):
    """Schema for sponsor in API responses."""

    sponsor_id: str
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    website_url: str | None = None
    logo_url: str | None = None
    status: str = "active"
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
