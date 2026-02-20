"""Current-user routes — /api/v1/users/me.

These routes let an authenticated user manage their own profile
and view their account details.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from fittrack.api.deps import get_current_user
from fittrack.api.schemas.profiles import ProfileCreate, ProfileUpdate
from fittrack.repositories.profile_repository import ProfileRepository
from fittrack.repositories.user_repository import UserRepository
from fittrack.services.profiles import ProfileError, ProfileService

router = APIRouter(prefix="/api/v1/users/me", tags=["me"])


def _get_profile_service() -> ProfileService:
    from fittrack.core.database import get_pool

    pool = get_pool()
    return ProfileService(
        profile_repo=ProfileRepository(pool=pool),
        user_repo=UserRepository(pool=pool),
    )


@router.get("")
def get_me(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the current user's account merged with their profile."""
    svc = _get_profile_service()
    user_id = user.get("sub", "")
    try:
        return svc.get_user_with_profile(user_id)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


@router.get("/profile")
def get_my_profile(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Return the current user's profile (or 404 if none exists)."""
    svc = _get_profile_service()
    user_id = user.get("sub", "")
    profile = svc.get_profile_by_user_id(user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile found. Create one via PUT /api/v1/users/me/profile",
        )
    return profile


@router.put("/profile")
def upsert_my_profile(
    body: ProfileCreate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create or update the authenticated user's profile.

    If the user already has a profile, update it.
    Otherwise, create a new one.
    """
    svc = _get_profile_service()
    user_id = user.get("sub", "")
    data = body.model_dump(exclude_none=True, mode="json")
    data.pop("user_id", None)  # ignore any client-sent user_id

    existing = svc.get_profile_by_user_id(user_id)
    try:
        if existing:
            profile_id = existing.get("profile_id", "")
            return svc.update_profile(
                profile_id=profile_id,
                data=data,
                user_id=user_id,
            )
        return svc.create_profile(user_id=user_id, data=data)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


@router.patch("/profile")
def patch_my_profile(
    body: ProfileUpdate,
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Partially update the authenticated user's profile."""
    svc = _get_profile_service()
    user_id = user.get("sub", "")
    profile = svc.get_profile_by_user_id(user_id)
    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="No profile to update. Create one via PUT /api/v1/users/me/profile",
        )

    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        return svc.update_profile(
            profile_id=profile.get("profile_id", ""),
            data=data,
            user_id=user_id,
        )
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc


@router.get("/profile/complete")
def check_profile_completeness(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Check whether the current user has a complete profile."""
    svc = _get_profile_service()
    user_id = user.get("sub", "")
    complete = svc.check_profile_complete_for_user(user_id)
    return {"user_id": user_id, "profile_complete": complete}


# ── Public profile view ─────────────────────────────────────────────

public_router = APIRouter(prefix="/api/v1/users", tags=["users"])


@public_router.get("/{user_id}/public")
def get_public_profile(user_id: str) -> dict[str, Any]:
    """Get a public view of any user's profile."""
    svc = _get_profile_service()
    try:
        return svc.get_public_profile(user_id)
    except ProfileError as exc:
        raise HTTPException(
            status_code=exc.status_code, detail=exc.detail,
        ) from exc
