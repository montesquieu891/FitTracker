"""API middleware: CORS, security headers, rate limiting, request logging."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from fittrack.core.context import set_correlation_id

logger = logging.getLogger(__name__)

# ── In-memory rate limit store (per-process; swap for Redis in prod) ───

_rate_buckets: dict[str, list[float]] = defaultdict(list)

RATE_LIMIT_WINDOW = 60  # seconds


def _check_rate_limit(key: str, limit: int) -> tuple[bool, int]:
    """Return (allowed, remaining) for a given key and per-minute limit."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    bucket = _rate_buckets[key]
    # Prune old entries
    _rate_buckets[key] = bucket = [t for t in bucket if t > window_start]
    if len(bucket) >= limit:
        return False, 0
    bucket.append(now)
    return True, limit - len(bucket)


def _get_client_key(request: Request) -> str:
    """Build rate-limit key from client IP."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ── Security Headers ───────────────────────────────────────────────

SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}

HSTS_HEADER = "max-age=31536000; includeSubDomains"

CSP_HEADER = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'"
)


def setup_middleware(app: FastAPI) -> None:
    """Attach all middleware to the FastAPI app."""
    settings = getattr(app.state, "settings", None)
    is_prod = settings.is_production if settings else False

    # GZip compression (>500 bytes)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS
    origins = _get_cors_origins(settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def security_and_logging(  # type: ignore[no-untyped-def]
        request: Request, call_next
    ):
        # ── Correlation ID ──────────────────────────────────────
        correlation_id = request.headers.get("x-correlation-id", uuid.uuid4().hex[:12])
        set_correlation_id(correlation_id)

        # ── Dev endpoint guard ──────────────────────────────────
        if is_prod and request.url.path.startswith("/api/v1/dev"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

        # ── Static file guard in production ─────────────────────
        if is_prod and request.url.path.startswith("/static"):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"},
            )

        # ── Rate Limiting ───────────────────────────────────────
        rate_result = _apply_rate_limit(request, settings)
        if rate_result is not None:
            return rate_result

        # ── Process request ─────────────────────────────────────
        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000

        # ── Add response headers ────────────────────────────────
        response.headers["X-Request-ID"] = correlation_id
        response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"

        # Security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        if is_prod:
            response.headers["Strict-Transport-Security"] = HSTS_HEADER
            response.headers["Content-Security-Policy"] = CSP_HEADER

        # ── Request logging ─────────────────────────────────────
        logger.info(
            "[%s] %s %s → %d (%.1fms)",
            correlation_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
        )

        return response


def _get_cors_origins(settings: Any) -> list[str]:
    """Resolve CORS origins from settings."""
    if settings is None:
        return ["*"]
    if hasattr(settings, "cors_origin_list"):
        return list(settings.cors_origin_list)
    return ["*"] if not settings.is_production else []


def _apply_rate_limit(request: Request, settings: Any) -> JSONResponse | None:
    """Apply tiered rate limiting. Returns error response if limit exceeded."""
    if settings is None or getattr(settings, "is_testing", False):
        return None

    # Skip rate limiting for health checks
    if request.url.path in ("/health", "/health/ready", "/health/live"):
        return None

    # Determine tier
    auth_header = request.headers.get("authorization", "")
    client_key = _get_client_key(request)

    if auth_header.startswith("Bearer "):
        # Authenticated request — check for admin role via JWT
        from fittrack.core.security import decode_token_safe

        token = auth_header.split(" ", 1)[1]
        payload = decode_token_safe(token)
        if payload and payload.get("role") == "admin":
            limit = getattr(settings, "rate_limit_admin", 500)
            rate_key = f"admin:{payload.get('sub', client_key)}"
        else:
            user_id = payload.get("sub", client_key) if payload else client_key
            limit = getattr(settings, "rate_limit_user", 100)
            rate_key = f"user:{user_id}"
    else:
        limit = getattr(settings, "rate_limit_anonymous", 10)
        rate_key = f"anon:{client_key}"

    allowed, remaining = _check_rate_limit(rate_key, limit)
    if not allowed:
        return JSONResponse(
            status_code=429,
            content={
                "type": "about:blank",
                "title": "Too Many Requests",
                "status": 429,
                "detail": f"Rate limit exceeded. Max {limit} requests per minute.",
            },
            headers={
                "Retry-After": str(RATE_LIMIT_WINDOW),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )
    return None


def rfc7807_error_response(
    status: int,
    title: str,
    detail: str,
    type_uri: str = "about:blank",
    instance: str | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build an RFC 7807 Problem Details JSON response."""
    body: dict[str, Any] = {
        "type": type_uri,
        "title": title,
        "status": status,
        "detail": detail,
    }
    if instance:
        body["instance"] = instance
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body)
