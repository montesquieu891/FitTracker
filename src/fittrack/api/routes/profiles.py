"""Profile CRUD routes — /api/v1/profiles.

Also includes ``/api/v1/users/me`` endpoints for the current user's
own profile management.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user
from fittrack.api.schemas.profiles import ProfileCreate, ProfileUpdate
from fittrack.repositories.profile_repository import ProfileRepository
from fittrack.repositories.user_repository import UserRepository
from fittrack.services.profiles import ProfileError, ProfileService

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


def _get_profile_service() -> ProfileService:
    from fittrack.core.database import get_pool

    pool = get_pool()
    return ProfileService(
        profile_repo=ProfileRepository(pool=pool),
        user_repo=UserRepository(pool=pool),
    )


# ── Collection endpoints ────────────────────────────────────────────


@router.get("")
def list_profiles(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    tier_code: str | None = None,
) -> dict[str, Any]:
    """List profiles with pagination and optional tier filter."""
    svc = _get_profile_service()
    try:
        return svc.list_profiles(page=page, limit=limit, tier_code=tier_code)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


@router.post("", status_code=201)
def create_profile(
    body: ProfileCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new profile with computed tier code."""
    svc = _get_profile_service()
    data = body.model_dump(exclude_none=True, mode="json")
    user_id = data.pop("user_id", None) or user.get("sub", "")
    try:
        return svc.create_profile(user_id=user_id, data=data)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


# ── Single-profile endpoints ────────────────────────────────────────


@router.get("/{profile_id}")
def get_profile(profile_id: str) -> dict[str, Any]:
    """Get a profile by ID."""
    svc = _get_profile_service()
    try:
        return svc.get_profile(profile_id)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


@router.put("/{profile_id}")
def update_profile(
    profile_id: str,
    body: ProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Update a profile, with ownership check and tier recomputation."""
    svc = _get_profile_service()
    data = body.model_dump(exclude_none=True)
    try:
        return svc.update_profile(
            profile_id=profile_id,
            data=data,
            user_id=user.get("sub"),
        )
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc
