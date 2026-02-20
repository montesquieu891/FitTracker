"""Notification routes — /api/v1/notifications.

User-facing notification endpoints for listing, reading,
and checking unread counts.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user, get_current_user_id

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _get_service():
    """Build NotificationService with real repository."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.notification_repository import (
        NotificationRepository,
    )
    from fittrack.services.notifications import NotificationService

    pool = get_pool()
    return NotificationService(
        notification_repo=NotificationRepository(pool=pool),
    )


@router.get("")
def list_notifications(
    is_read: bool | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get user's notifications with optional read/unread filter."""
    svc = _get_service()
    return svc.get_user_notifications(
        user_id=user_id,
        is_read=is_read,
        page=page,
        limit=limit,
    )


@router.get("/unread-count")
def get_unread_count(
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get count of unread notifications."""
    svc = _get_service()
    count = svc.get_unread_count(user_id)
    return {"unread_count": count}


@router.get("/{notification_id}")
def get_notification(
    notification_id: str,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Get a specific notification."""
    from fittrack.services.notifications import NotificationError

    svc = _get_service()
    try:
        notification = svc.get_notification(notification_id)
    except NotificationError as e:
        raise HTTPException(
            status_code=e.status_code, detail=e.detail
        ) from e

    # Ensure user can only see their own notifications
    if notification.get("user_id") != current_user.get("sub"):
        raise HTTPException(status_code=403, detail="Access denied")

    return notification


@router.put("/{notification_id}/read")
def mark_as_read(
    notification_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Mark a notification as read."""
    from fittrack.services.notifications import NotificationError

    svc = _get_service()
    try:
        return svc.mark_as_read(notification_id, user_id)
    except NotificationError as e:
        raise HTTPException(
            status_code=e.status_code, detail=e.detail
        ) from e
