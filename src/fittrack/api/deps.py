"""Dependency injection for FastAPI routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, Header, HTTPException, Query

from fittrack.core.database import get_pool
from fittrack.core.security import decode_token_safe


def get_db_pool():  # type: ignore[no-untyped-def]
    """Dependency that provides the Oracle connection pool."""
    return get_pool()


@dataclass
class PaginationParams:
    """Pagination parameters parsed from query string."""

    page: int
    limit: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def get_pagination(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Parse pagination query parameters."""
    return PaginationParams(page=page, limit=limit)


# ── Auth Dependencies ───────────────────────────────────────────────


def get_current_user(
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """Extract and validate JWT from Authorization header.

    Returns the decoded token payload (contains sub, role, type, etc.).
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Expect "Bearer <token>"
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    payload = decode_token_safe(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=401,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


def require_role(*roles: str):  # type: ignore[no-untyped-def]
    """Dependency factory: require the current user to have one of the specified roles."""

    def checker(
        current_user: dict[str, Any] = Depends(get_current_user),
    ) -> dict[str, Any]:
        user_role = current_user.get("role", "user")
        if user_role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Insufficient permissions. Required: {', '.join(roles)}",
            )
        return current_user

    return checker


def require_admin(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Require admin role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )
    return current_user


def get_current_user_id(
    current_user: dict[str, Any] = Depends(get_current_user),
) -> str:
    """Extract user_id from the current authenticated user."""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    return str(user_id)
