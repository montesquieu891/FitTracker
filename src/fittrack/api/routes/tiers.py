"""Tier routes — /api/v1/tiers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from fittrack.services.tiers import (
    TierService,
    enumerate_tiers,
    validate_tier_code,
)

router = APIRouter(prefix="/api/v1/tiers", tags=["tiers"])


def _get_tier_service() -> TierService:
    from fittrack.core.database import get_pool
    from fittrack.repositories.profile_repository import ProfileRepository

    pool = get_pool()
    return TierService(profile_repo=ProfileRepository(pool=pool))


@router.get("")
def list_tiers(
    include_counts: bool = False,
) -> dict[str, Any]:
    """List all 30 competition tiers.

    Use ``?include_counts=true`` to include user counts per tier
    (requires database access).
    """
    if include_counts:
        svc = _get_tier_service()
        items = svc.list_all_tiers_with_counts()
    else:
        items = enumerate_tiers()

    return {"items": items, "total": len(items)}


@router.get("/{tier_code}")
def get_tier(tier_code: str) -> dict[str, Any]:
    """Get details for a single tier, including user count."""
    if not validate_tier_code(tier_code):
        raise HTTPException(
            status_code=404,
            detail=f"Invalid tier code: {tier_code!r}",
        )

    svc = _get_tier_service()
    try:
        return svc.get_tier_with_user_count(tier_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
