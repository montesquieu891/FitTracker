"""Shared schemas used across all entity schemas."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginationMeta(BaseModel):
    """Pagination metadata in list responses."""

    page: int
    limit: int
    total_items: int
    total_pages: int


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    pagination: PaginationMeta


class ErrorResponse(BaseModel):
    """RFC 7807 Problem Details error response."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    environment: str
    database: str | None = None


class MessageResponse(BaseModel):
    """Simple message response."""

    message: str
    detail: dict[str, Any] | None = None
