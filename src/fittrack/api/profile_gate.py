"""Profile gate middleware — blocks users without a complete profile.

Unauthenticated requests and certain paths (auth, health, dev, tiers,
profile creation) are allowed through.  Authenticated users without a
complete profile receive a 403 response prompting them to complete setup.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from fittrack.core.security import decode_token_safe

logger = logging.getLogger(__name__)

# Paths that are always allowed, even without a complete profile.
# Matched by prefix — e.g. "/api/v1/auth/login" starts with "/api/v1/auth".
ALLOWED_PREFIXES: tuple[str, ...] = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth",
    "/api/v1/dev",
    "/api/v1/tiers",
    "/static",
    "/test",
)

# These specific paths (exact or prefix) allow profile creation / viewing
PROFILE_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/api/v1/profiles",
    "/api/v1/users/me",
)


def _is_allowed_path(path: str) -> bool:
    """Check if the request path is in the always-allowed list."""
    return any(path.startswith(prefix) for prefix in ALLOWED_PREFIXES)


def _is_profile_path(path: str) -> bool:
    """Check if the request path is a profile-related path."""
    return any(path.startswith(prefix) for prefix in PROFILE_ALLOWED_PREFIXES)


def _is_get_request(method: str) -> bool:
    """GET requests to most endpoints are read-only and safe to allow."""
    return method.upper() == "GET"


async def profile_gate_middleware(
    request: Request,
    call_next: Any,
) -> Any:
    """Middleware that blocks authenticated users without complete profiles.

    Allows:
    - Unauthenticated requests (they'll hit auth middleware separately)
    - Requests to whitelisted paths (auth, health, dev, docs, tiers)
    - Requests to profile endpoints (so users can create/update profiles)
    - GET requests (read-only operations)

    Blocks:
    - Authenticated POST/PUT/PATCH/DELETE to feature endpoints
      when the user has no complete profile
    """
    path = request.url.path

    # Skip in testing mode (tests manage their own gate checks)
    settings = getattr(request.app.state, "settings", None)
    if settings and getattr(settings, "is_testing", False):
        return await call_next(request)

    # Always allow whitelisted paths
    if _is_allowed_path(path):
        return await call_next(request)

    # Always allow profile-related paths
    if _is_profile_path(path):
        return await call_next(request)

    # Allow GET requests (read-only)
    if _is_get_request(request.method):
        return await call_next(request)

    # Check if user is authenticated
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        # Not authenticated — let the route handler deal with it
        return await call_next(request)

    token = auth_header.split(" ", 1)[1]
    payload = decode_token_safe(token)
    if payload is None or payload.get("type") != "access":
        return await call_next(request)

    # Admin users bypass the profile gate
    if payload.get("role") == "admin":
        return await call_next(request)

    # Check profile completeness
    user_id = payload.get("sub", "")
    if not user_id:
        return await call_next(request)

    try:
        from fittrack.core.database import get_pool
        from fittrack.repositories.profile_repository import (
            ProfileRepository,
        )

        pool = get_pool()
        if pool is None:
            # No DB pool — skip gate (dev / test mode)
            return await call_next(request)

        repo = ProfileRepository(pool=pool)
        profile = repo.find_by_user_id(user_id)

        if profile is None:
            return _profile_incomplete_response(
                "No profile found. Please create your profile first.",
            )

        from fittrack.services.profiles import REQUIRED_PROFILE_FIELDS

        for field in REQUIRED_PROFILE_FIELDS:
            value = profile.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                return _profile_incomplete_response(
                    "Profile is incomplete. "
                    "Please complete your profile to access this feature.",
                )

    except Exception:
        # If we can't check, let the request through
        logger.exception("Profile gate error — allowing request through")
        return await call_next(request)

    return await call_next(request)


def _profile_incomplete_response(detail: str) -> JSONResponse:
    """Return a 403 response indicating profile is incomplete."""
    return JSONResponse(
        status_code=403,
        content={
            "type": "about:blank",
            "title": "Profile Incomplete",
            "status": 403,
            "detail": detail,
            "action": "Create or complete your profile at PUT /api/v1/users/me/profile",
        },
    )
