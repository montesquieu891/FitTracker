"""Profile entity schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProfileCreate(BaseModel):
    """Schema for creating a profile."""

    user_id: str
    display_name: str = Field(min_length=2, max_length=50)
    date_of_birth: date
    state_of_residence: str = Field(min_length=2, max_length=2)
    biological_sex: str = Field(pattern=r"^(male|female)$")
    age_bracket: str = Field(pattern=r"^(18-29|30-39|40-49|50-59|60\+)$")
    fitness_level: str = Field(pattern=r"^(beginner|intermediate|advanced)$")
    height_inches: int | None = Field(default=None, ge=36, le=96)
    weight_pounds: int | None = Field(default=None, ge=50, le=700)
    goals: list[str] | None = None


class ProfileUpdate(BaseModel):
    """Schema for updating a profile."""

    display_name: str | None = Field(default=None, min_length=2, max_length=50)
    biological_sex: str | None = Field(default=None, pattern=r"^(male|female)$")
    age_bracket: str | None = Field(default=None, pattern=r"^(18-29|30-39|40-49|50-59|60\+)$")
    fitness_level: str | None = Field(default=None, pattern=r"^(beginner|intermediate|advanced)$")
    height_inches: int | None = Field(default=None, ge=36, le=96)
    weight_pounds: int | None = Field(default=None, ge=50, le=700)
    goals: list[str] | None = None


class ProfileResponse(BaseModel):
    """Schema for profile in API responses."""

    profile_id: str
    user_id: str
    display_name: str
    date_of_birth: date | None = None
    state_of_residence: str | None = None
    biological_sex: str | None = None
    age_bracket: str | None = None
    fitness_level: str | None = None
    tier_code: str | None = None
    height_inches: int | None = None
    weight_pounds: int | None = None
    goals: Any = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
