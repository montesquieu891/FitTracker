"""Points routes — /api/v1/points.

Endpoints for checking balance, viewing transaction history, and weekly streak.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Query

from fittrack.api.deps import get_current_user, get_current_user_id

if TYPE_CHECKING:
    from fittrack.services.points import PointsService

router = APIRouter(prefix="/api/v1/points", tags=["points"])


def _get_points_service() -> PointsService:
    from fittrack.core.database import get_pool
    from fittrack.repositories.activity_repository import ActivityRepository
    from fittrack.repositories.transaction_repository import TransactionRepository
    from fittrack.repositories.user_repository import UserRepository
    from fittrack.services.points import PointsService

    pool = get_pool()
    return PointsService(
        transaction_repo=TransactionRepository(pool),
        user_repo=UserRepository(pool),
        activity_repo=ActivityRepository(pool),
    )


@router.get("/balance")
def get_balance(
    user_id: str = Depends(get_current_user_id),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current user's point balance."""
    service = _get_points_service()
    balance = service.get_balance(user_id)
    earned = service.get_points_earned(user_id)
    return {
        "user_id": user_id,
        "point_balance": balance,
        "points_earned": earned,
    }


@router.get("/transactions")
def get_transactions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get the current user's point transaction history."""
    service = _get_points_service()
    offset = (page - 1) * limit
    items = service.get_transaction_history(user_id, limit=limit, offset=offset)
    return {
        "items": items,
        "pagination": {
            "page": page,
            "limit": limit,
        },
    }


@router.get("/daily")
def get_daily_status(
    user_id: str = Depends(get_current_user_id),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get today's point earning status (for daily cap tracking)."""
    service = _get_points_service()
    ctx = service.get_daily_context(user_id)
    from fittrack.core.constants import DAILY_POINT_CAP

    return {
        "user_id": user_id,
        "points_earned_today": ctx.get("points_earned_today", 0),
        "daily_cap": DAILY_POINT_CAP,
        "remaining": max(0, DAILY_POINT_CAP - ctx.get("points_earned_today", 0)),
        "workouts_today": ctx.get("workouts_today", 0),
        "steps_today": ctx.get("steps_today", 0),
    }


@router.get("/streak")
def get_weekly_streak(
    user_id: str = Depends(get_current_user_id),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Check the current user's weekly streak status."""
    service = _get_points_service()
    return service.check_weekly_streak(user_id)
