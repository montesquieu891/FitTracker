"""Admin user management service.

Provides user search, status management (suspend/ban/activate),
manual point adjustments with audit logging.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fittrack.core.constants import USER_ROLES, USER_STATUSES

logger = logging.getLogger(__name__)


class AdminUserError(Exception):
    """Raised on admin user operation failures."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Valid status transitions for admin actions
ADMIN_STATUS_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["active", "banned"],
    "active": ["suspended", "banned"],
    "suspended": ["active", "banned"],
    "banned": ["active"],
}


class AdminUserService:
    """Service for admin-level user management operations."""

    def __init__(
        self,
        user_repo: Any,
        profile_repo: Any,
        transaction_repo: Any,
        action_log_repo: Any,
    ) -> None:
        self.user_repo = user_repo
        self.profile_repo = profile_repo
        self.transaction_repo = transaction_repo
        self.action_log_repo = action_log_repo

    # ── Search ───────────────────────────────────────────────────

    def search_users(
        self,
        *,
        email: str | None = None,
        display_name: str | None = None,
        status: str | None = None,
        role: str | None = None,
        tier_code: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Search users by various criteria with pagination."""
        if status and status not in USER_STATUSES:
            raise AdminUserError(
                f"Invalid status: {status}. Valid: {USER_STATUSES}", 400
            )
        if role and role not in USER_ROLES:
            raise AdminUserError(
                f"Invalid role: {role}. Valid: {USER_ROLES}", 400
            )

        filters: dict[str, Any] = {}
        if email:
            filters["email"] = email
        if status:
            filters["status"] = status
        if role:
            filters["role"] = role

        offset = (page - 1) * limit
        users = self.user_repo.find_all(
            limit=limit, offset=offset, filters=filters if filters else None
        )
        total = self.user_repo.count(filters=filters if filters else None)

        # If searching by display_name or tier_code, we need to
        # cross-reference profiles
        if display_name or tier_code:
            users = self._filter_by_profile(
                users,
                display_name=display_name,
                tier_code=tier_code,
            )
            total = len(users)

        total_pages = max(1, (total + limit - 1) // limit)
        return {
            "items": users,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }

    def _filter_by_profile(
        self,
        users: list[dict[str, Any]],
        display_name: str | None = None,
        tier_code: str | None = None,
    ) -> list[dict[str, Any]]:
        """Filter users by profile attributes."""
        filtered = []
        for user in users:
            user_id = user.get("user_id")
            if not user_id:
                continue
            profiles = self.profile_repo.find_by_field("user_id", user_id)
            if not profiles:
                continue
            profile = profiles[0]
            if display_name:
                pname = (profile.get("display_name") or "").lower()
                if display_name.lower() not in pname:
                    continue
            if tier_code and profile.get("tier_code") != tier_code:
                continue
            user["profile"] = profile
            filtered.append(user)
        return filtered

    # ── Status Management ────────────────────────────────────────

    def change_user_status(
        self,
        user_id: str,
        new_status: str,
        admin_id: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Change a user's status (suspend/ban/activate)."""
        if new_status not in USER_STATUSES:
            raise AdminUserError(
                f"Invalid status: {new_status}. Valid: {USER_STATUSES}", 400
            )

        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AdminUserError("User not found", 404)

        current_status = user.get("status", "pending")
        allowed = ADMIN_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed:
            raise AdminUserError(
                f"Cannot transition from '{current_status}' to "
                f"'{new_status}'. Allowed: {allowed}",
                409,
            )

        now = datetime.now(tz=UTC).isoformat()
        self.user_repo.update(
            user_id, data={"status": new_status, "updated_at": now}
        )

        # Log the action
        self._log_action(
            admin_id=admin_id,
            action_type="status_change",
            target_user_id=user_id,
            details={
                "old_status": current_status,
                "new_status": new_status,
                "reason": reason,
            },
        )

        logger.info(
            "Admin %s changed user %s status: %s → %s (reason: %s)",
            admin_id,
            user_id,
            current_status,
            new_status,
            reason,
        )

        return {
            "user_id": user_id,
            "old_status": current_status,
            "new_status": new_status,
            "reason": reason,
            "changed_by": admin_id,
            "changed_at": now,
        }

    def suspend_user(
        self, user_id: str, admin_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Suspend a user."""
        return self.change_user_status(user_id, "suspended", admin_id, reason)

    def ban_user(
        self, user_id: str, admin_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Ban a user."""
        return self.change_user_status(user_id, "banned", admin_id, reason)

    def activate_user(
        self, user_id: str, admin_id: str, reason: str = ""
    ) -> dict[str, Any]:
        """Activate a user."""
        return self.change_user_status(user_id, "active", admin_id, reason)

    # ── Point Adjustment ─────────────────────────────────────────

    def adjust_points(
        self,
        user_id: str,
        amount: int,
        reason: str,
        admin_id: str,
    ) -> dict[str, Any]:
        """Manually adjust a user's point balance.

        Positive amount adds points, negative deducts.
        Balance cannot go below 0.
        """
        if not reason:
            raise AdminUserError("Reason is required for point adjustments")

        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AdminUserError("User not found", 404)

        current_balance = user.get("point_balance", 0)
        new_balance = max(0, current_balance + amount)

        # Create the transaction record
        txn_id = uuid.uuid4().hex
        now = datetime.now(tz=UTC).isoformat()
        txn_data = {
            "user_id": user_id,
            "transaction_type": "adjust",
            "amount": amount,
            "balance_after": new_balance,
            "reference_type": "admin_adjustment",
            "reference_id": admin_id,
            "description": reason,
            "created_at": now,
        }
        self.transaction_repo.create(data=txn_data, new_id=txn_id)

        # Update user balance
        self.user_repo.update(
            user_id, data={"point_balance": new_balance, "updated_at": now}
        )

        # Log the action
        self._log_action(
            admin_id=admin_id,
            action_type="point_adjustment",
            target_user_id=user_id,
            details={
                "amount": amount,
                "old_balance": current_balance,
                "new_balance": new_balance,
                "reason": reason,
            },
        )

        logger.info(
            "Admin %s adjusted points for user %s: %+d (balance: %d → %d)",
            admin_id,
            user_id,
            amount,
            current_balance,
            new_balance,
        )

        return {
            "user_id": user_id,
            "transaction_id": txn_id,
            "amount": amount,
            "old_balance": current_balance,
            "new_balance": new_balance,
            "reason": reason,
            "adjusted_by": admin_id,
            "adjusted_at": now,
        }

    # ── Action Log ───────────────────────────────────────────────

    def _log_action(
        self,
        admin_id: str,
        action_type: str,
        target_user_id: str,
        details: dict[str, Any] | None = None,
    ) -> str:
        """Log an admin action for audit trail."""
        log_id = uuid.uuid4().hex
        log_data = {
            "admin_user_id": admin_id,
            "action_type": action_type,
            "target_user_id": target_user_id,
            "details": str(details) if details else "",
            "created_at": datetime.now(tz=UTC).isoformat(),
        }
        self.action_log_repo.create(data=log_data, new_id=log_id)
        return log_id

    def get_action_log(
        self,
        *,
        admin_id: str | None = None,
        target_user_id: str | None = None,
        action_type: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Retrieve admin action logs with optional filters."""
        filters: dict[str, Any] = {}
        if admin_id:
            filters["admin_user_id"] = admin_id
        if target_user_id:
            filters["target_user_id"] = target_user_id
        if action_type:
            filters["action_type"] = action_type

        offset = (page - 1) * limit
        items = self.action_log_repo.find_all(
            limit=limit,
            offset=offset,
            filters=filters if filters else None,
        )
        total = self.action_log_repo.count(
            filters=filters if filters else None
        )
        total_pages = max(1, (total + limit - 1) // limit)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }

    def get_user_detail(self, user_id: str) -> dict[str, Any]:
        """Get detailed user info including profile and recent activity."""
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise AdminUserError("User not found", 404)

        # Attach profile if exists
        profiles = self.profile_repo.find_by_field("user_id", user_id)
        if profiles:
            user["profile"] = profiles[0]

        # Get recent transactions
        txns = self.transaction_repo.find_all(
            limit=10, offset=0, filters={"user_id": user_id}
        )
        user["recent_transactions"] = txns

        return user
