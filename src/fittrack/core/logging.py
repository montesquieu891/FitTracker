"""Structured logging configuration with JSON output and sensitive field redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

# Fields whose values should be redacted in log output
SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"token", re.IGNORECASE),
    re.compile(r"authorization", re.IGNORECASE),
    re.compile(r"api[_-]?key", re.IGNORECASE),
    re.compile(r"credit[_-]?card", re.IGNORECASE),
    re.compile(r"ssn", re.IGNORECASE),
]

REDACTED = "***REDACTED***"


def is_sensitive_key(key: str) -> bool:
    """Check if a key name matches any sensitive pattern."""
    return any(p.search(key) for p in SENSITIVE_PATTERNS)


def redact_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive fields from a dictionary."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if is_sensitive_key(key):
            result[key] = REDACTED
        elif isinstance(value, dict):
            result[key] = redact_dict(value)
        elif isinstance(value, list):
            result[key] = [redact_dict(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def redact_string(text: str) -> str:
    """Redact known sensitive patterns from freeform log text."""
    # Redact Authorization: Bearer xxx
    text = re.sub(
        r"(Authorization:\s*Bearer\s+)\S+",
        r"\1" + REDACTED,
        text,
        flags=re.IGNORECASE,
    )
    # Redact password=xxx or password: xxx
    text = re.sub(
        r"(password[\s=:]+)\S+",
        r"\1" + REDACTED,
        text,
        flags=re.IGNORECASE,
    )
    # Redact token=xxx (query param style)
    text = re.sub(
        r"(token[\s=:]+)\S+",
        r"\1" + REDACTED,
        text,
        flags=re.IGNORECASE,
    )
    return text


class JSONFormatter(logging.Formatter):
    """Structured JSON log formatter with sensitive field redaction."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact_string(record.getMessage()),
        }

        # Add correlation_id if present on the record
        correlation_id = getattr(record, "correlation_id", None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add source location
        log_entry["source"] = {
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
            }

        # Add extra fields (redacted)
        extras = {
            k: v
            for k, v in record.__dict__.items()
            if k not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__
            and k not in ("message", "correlation_id")
        }
        if extras:
            log_entry["extra"] = redact_dict(extras)

        return json.dumps(log_entry, default=str)


class RedactingFormatter(logging.Formatter):
    """Standard text formatter with sensitive field redaction."""

    def __init__(self, fmt: str | None = None, datefmt: str | None = None) -> None:
        super().__init__(
            fmt=fmt or "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt=datefmt or "%Y-%m-%d %H:%M:%S",
        )

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return redact_string(original)


class CorrelationFilter(logging.Filter):
    """Logging filter that adds correlation_id from contextvars."""

    def filter(self, record: logging.LogRecord) -> bool:
        from fittrack.core.context import get_correlation_id

        record.correlation_id = get_correlation_id()  # noqa: F841
        return True


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Configure application-wide logging.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: "json" for structured JSON output, "text" for human-readable.
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root.handlers.clear()

    handler = logging.StreamHandler()

    if log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(RedactingFormatter())

    # Add correlation ID filter
    handler.addFilter(CorrelationFilter())

    root.addHandler(handler)

    # Quiet noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("watchfiles").setLevel(logging.WARNING)
