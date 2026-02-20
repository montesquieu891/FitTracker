"""Request context management via contextvars — correlation IDs, etc."""

from __future__ import annotations

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str) -> None:
    """Set the correlation ID for the current request context."""
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    """Get the correlation ID for the current request context."""
    return _correlation_id.get()
