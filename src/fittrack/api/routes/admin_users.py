"""Admin user management routes — /api/v1/admin/users.

Provides user search, status management, and point adjustments.
All endpoints require admin role.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import require_admin

router = APIRouter(prefix="/api/v1/admin/users", tags=["admin-users"])


def _get_service():
    """Build AdminUserService with real repositories."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.admin_action_log_repository import (
        AdminActionLogRepository,
    )
    from fittrack.repositories.profile_repository import ProfileRepository
    from fittrack.repositories.transaction_repository import (
        TransactionRepository,
    )
    from fittrack.repositories.user_repository import UserRepository
    from fittrack.services.admin_users import AdminUserService

    pool = get_pool()
    return AdminUserService(
        user_repo=UserRepository(pool=pool),
        profile_repo=ProfileRepository(pool=pool),
        transaction_repo=TransactionRepository(pool=pool),
        action_log_repo=AdminActionLogRepository(pool=pool),
    )


@router.get("")
def search_users(
    email: str | None = None,
    display_name: str | None = None,
    status: str | None = None,
    role: str | None = None,
    tier_code: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Search/list users with filters (admin only)."""
    from fittrack.services.admin_users import AdminUserError

    svc = _get_service()
    try:
        return svc.search_users(
            email=email,
            display_name=display_name,
            status=status,
            role=role,
            tier_code=tier_code,
            page=page,
            limit=limit,
        )
    except AdminUserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{user_id}")
def get_user_detail(
    user_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Get detailed user info including profile (admin only)."""
    from fittrack.services.admin_users import AdminUserError

    svc = _get_service()
    try:
        return svc.get_user_detail(user_id)
    except AdminUserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.put("/{user_id}/status")
def change_user_status(
    user_id: str,
    new_status: str = Query(..., description="New status"),
    reason: str = Query(default="", description="Reason for change"),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Suspend, ban, or activate a user (admin only)."""
    from fittrack.services.admin_users import AdminUserError

    svc = _get_service()
    try:
        return svc.change_user_status(
            user_id=user_id,
            new_status=new_status,
            admin_id=admin.get("sub", ""),
            reason=reason,
        )
    except AdminUserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{user_id}/adjust-points")
def adjust_points(
    user_id: str,
    amount: int = Query(..., description="Points to add (positive) or remove (negative)"),
    reason: str = Query(..., min_length=1, description="Reason for adjustment"),
    admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Manually adjust a user's point balance (admin only)."""
    from fittrack.services.admin_users import AdminUserError

    svc = _get_service()
    try:
        return svc.adjust_points(
            user_id=user_id,
            amount=amount,
            reason=reason,
            admin_id=admin.get("sub", ""),
        )
    except AdminUserError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{user_id}/actions")
def get_user_actions(
    user_id: str,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Get admin action log for a specific user (admin only)."""
    svc = _get_service()
    return svc.get_action_log(
        target_user_id=user_id, page=page, limit=limit
    )
