"""Leaderboard routes — /api/v1/leaderboards.

Endpoints for viewing tier-scoped leaderboards and user rankings.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user_id

router = APIRouter(prefix="/api/v1/leaderboards", tags=["leaderboards"])


def _get_leaderboard_service():  # type: ignore[no-untyped-def]
    from fittrack.core.database import get_pool
    from fittrack.repositories.activity_repository import ActivityRepository
    from fittrack.repositories.profile_repository import ProfileRepository
    from fittrack.repositories.transaction_repository import TransactionRepository
    from fittrack.services.cache import CacheService
    from fittrack.services.leaderboard import LeaderboardService

    pool = get_pool()
    cache = CacheService()  # In-memory fallback for now
    return LeaderboardService(
        transaction_repo=TransactionRepository(pool),
        profile_repo=ProfileRepository(pool),
        activity_repo=ActivityRepository(pool),
        cache_service=cache,
    )


def _get_user_tier(user_id: str) -> str | None:
    """Look up the current user's tier code from their profile."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.profile_repository import ProfileRepository

    pool = get_pool()
    profile_repo = ProfileRepository(pool)
    profile = profile_repo.find_by_user_id(user_id)
    if profile:
        return profile.get("tier_code")
    return None


@router.get("/{period}")
def get_leaderboard(
    period: str,
    tier_code: str | None = Query(
        default=None,
        description="Filter by tier code. Defaults to user's tier if authenticated.",
    ),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get the leaderboard for a given period.

    Periods: daily, weekly, monthly, all_time.
    If no tier_code is specified, defaults to the authenticated user's tier.
    """
    from fittrack.services.leaderboard import LeaderboardError

    # Default to user's own tier
    if tier_code is None:
        tier_code = _get_user_tier(user_id)

    service = _get_leaderboard_service()
    try:
        return service.get_leaderboard(
            period=period,
            tier_code=tier_code,
            page=page,
            limit=limit,
        )
    except LeaderboardError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{period}/me")
def get_my_rank(
    period: str,
    tier_code: str | None = Query(
        default=None,
        description="Tier to check rank in. Defaults to user's tier.",
    ),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get the current user's rank and surrounding context.

    Returns the user's position plus ±10 positions around them.
    """
    from fittrack.services.leaderboard import LeaderboardError

    if tier_code is None:
        tier_code = _get_user_tier(user_id)

    service = _get_leaderboard_service()
    try:
        return service.get_user_rank(
            user_id=user_id,
            period=period,
            tier_code=tier_code,
        )
    except LeaderboardError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
