"""Admin analytics routes — /api/v1/admin/analytics.

Provides dashboard metrics, registration trends, activity metrics,
and drawing participation stats. All endpoints require admin role.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import require_admin

if TYPE_CHECKING:
    from fittrack.services.analytics import AnalyticsService

router = APIRouter(prefix="/api/v1/admin/analytics", tags=["admin-analytics"])


def _get_service() -> AnalyticsService:
    """Build AnalyticsService with real repositories."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.activity_repository import (
        ActivityRepository,
    )
    from fittrack.repositories.drawing_repository import DrawingRepository
    from fittrack.repositories.ticket_repository import TicketRepository
    from fittrack.repositories.transaction_repository import (
        TransactionRepository,
    )
    from fittrack.repositories.user_repository import UserRepository
    from fittrack.services.analytics import AnalyticsService

    pool = get_pool()
    return AnalyticsService(
        user_repo=UserRepository(pool=pool),
        activity_repo=ActivityRepository(pool=pool),
        drawing_repo=DrawingRepository(pool=pool),
        ticket_repo=TicketRepository(pool=pool),
        transaction_repo=TransactionRepository(pool=pool),
    )


@router.get("/overview")
def get_overview(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Dashboard overview metrics (admin only)."""
    from fittrack.services.analytics import AnalyticsError

    svc = _get_service()
    try:
        return svc.get_overview()
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/registrations")
def get_registration_trends(
    period: str = Query(default="daily", description="Bucket period: daily, weekly, monthly"),
    days: int = Query(default=30, ge=1, le=365),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Registration trend data (admin only)."""
    from fittrack.services.analytics import AnalyticsError

    svc = _get_service()
    try:
        return svc.get_registration_trends(period=period, days=days)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/activity")
def get_activity_metrics(
    days: int = Query(default=30, ge=1, le=365),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Activity metrics (admin only)."""
    from fittrack.services.analytics import AnalyticsError

    svc = _get_service()
    try:
        return svc.get_activity_metrics(days=days)
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/drawings")
def get_drawing_metrics(
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Drawing participation metrics (admin only)."""
    from fittrack.services.analytics import AnalyticsError

    svc = _get_service()
    try:
        return svc.get_drawing_metrics()
    except AnalyticsError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
