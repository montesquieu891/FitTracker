"""Tests for admin user service — search, suspend, ban, point adjustment."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from fittrack.services.admin_users import (
    ADMIN_STATUS_TRANSITIONS,
    AdminUserError,
    AdminUserService,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_service(
    *,
    users: list[dict[str, Any]] | None = None,
    profiles: list[dict[str, Any]] | None = None,
) -> AdminUserService:
    """Create an AdminUserService with mock repos."""
    user_repo = MagicMock()
    profile_repo = MagicMock()
    transaction_repo = MagicMock()
    action_log_repo = MagicMock()

    if users:
        user_repo.find_by_id.side_effect = lambda uid: next(
            (u for u in users if u.get("user_id") == uid), None
        )
        user_repo.find_all.return_value = users
        user_repo.count.return_value = len(users)
    else:
        user_repo.find_by_id.return_value = None
        user_repo.find_all.return_value = []
        user_repo.count.return_value = 0

    if profiles:
        profile_repo.find_by_field.side_effect = lambda field, val: [
            p for p in profiles if p.get(field) == val
        ]
    else:
        profile_repo.find_by_field.return_value = []

    svc = AdminUserService(
        user_repo=user_repo,
        profile_repo=profile_repo,
        transaction_repo=transaction_repo,
        action_log_repo=action_log_repo,
    )
    return svc


# ── Search Tests ─────────────────────────────────────────────────────


class TestSearchUsers:
    """Test user search functionality."""

    def test_search_all_users(self) -> None:
        users = [
            {"user_id": "u1", "email": "a@b.com", "status": "active"},
            {"user_id": "u2", "email": "c@d.com", "status": "active"},
        ]
        svc = _make_service(users=users)
        result = svc.search_users()
        assert result["pagination"]["total_items"] == 2
        assert len(result["items"]) == 2

    def test_search_by_email(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        svc = _make_service(users=users)
        svc.search_users(email="a@b.com")
        svc.user_repo.find_all.assert_called_once()

    def test_search_by_status(self) -> None:
        users = [
            {"user_id": "u1", "email": "a@b.com", "status": "suspended"},
        ]
        svc = _make_service(users=users)
        result = svc.search_users(status="suspended")
        assert result["items"] is not None

    def test_search_invalid_status(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="Invalid status"):
            svc.search_users(status="imaginary")

    def test_search_invalid_role(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="Invalid role"):
            svc.search_users(role="superuser")

    def test_search_by_display_name(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        profiles = [
            {
                "user_id": "u1",
                "display_name": "JohnDoe",
                "tier_code": "M-18-29-BEG",
            }
        ]
        svc = _make_service(users=users, profiles=profiles)
        result = svc.search_users(display_name="john")
        assert len(result["items"]) == 1

    def test_search_by_display_name_no_match(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        profiles = [
            {
                "user_id": "u1",
                "display_name": "JohnDoe",
                "tier_code": "M-18-29-BEG",
            }
        ]
        svc = _make_service(users=users, profiles=profiles)
        result = svc.search_users(display_name="alice")
        assert len(result["items"]) == 0

    def test_search_by_tier_code(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        profiles = [
            {
                "user_id": "u1",
                "display_name": "John",
                "tier_code": "M-18-29-BEG",
            }
        ]
        svc = _make_service(users=users, profiles=profiles)
        result = svc.search_users(tier_code="M-18-29-BEG")
        assert len(result["items"]) == 1

    def test_search_by_tier_code_no_match(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        profiles = [
            {
                "user_id": "u1",
                "display_name": "John",
                "tier_code": "M-18-29-BEG",
            }
        ]
        svc = _make_service(users=users, profiles=profiles)
        result = svc.search_users(tier_code="F-30-39-ADV")
        assert len(result["items"]) == 0

    def test_search_pagination(self) -> None:
        users = [
            {"user_id": f"u{i}", "email": f"u{i}@test.com", "status": "active"}
            for i in range(5)
        ]
        svc = _make_service(users=users)
        result = svc.search_users(page=1, limit=2)
        assert result["pagination"]["page"] == 1
        assert result["pagination"]["limit"] == 2


# ── Status Change Tests ──────────────────────────────────────────────


class TestChangeUserStatus:
    """Test user status management."""

    def test_suspend_active_user(self) -> None:
        users = [{"user_id": "u1", "status": "active", "email": "a@b.com"}]
        svc = _make_service(users=users)
        result = svc.suspend_user("u1", "admin1", "Policy violation")
        assert result["new_status"] == "suspended"
        assert result["old_status"] == "active"
        assert result["reason"] == "Policy violation"
        svc.user_repo.update.assert_called_once()
        svc.action_log_repo.create.assert_called_once()

    def test_ban_active_user(self) -> None:
        users = [{"user_id": "u1", "status": "active", "email": "a@b.com"}]
        svc = _make_service(users=users)
        result = svc.ban_user("u1", "admin1")
        assert result["new_status"] == "banned"

    def test_activate_suspended_user(self) -> None:
        users = [
            {"user_id": "u1", "status": "suspended", "email": "a@b.com"}
        ]
        svc = _make_service(users=users)
        result = svc.activate_user("u1", "admin1")
        assert result["new_status"] == "active"

    def test_activate_banned_user(self) -> None:
        users = [{"user_id": "u1", "status": "banned", "email": "a@b.com"}]
        svc = _make_service(users=users)
        result = svc.activate_user("u1", "admin1")
        assert result["new_status"] == "active"

    def test_invalid_transition_suspend_pending(self) -> None:
        users = [{"user_id": "u1", "status": "pending", "email": "a@b.com"}]
        svc = _make_service(users=users)
        with pytest.raises(AdminUserError, match="Cannot transition"):
            svc.suspend_user("u1", "admin1")

    def test_user_not_found(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="User not found"):
            svc.change_user_status("u999", "active", "admin1")

    def test_invalid_target_status(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="Invalid status"):
            svc.change_user_status("u1", "imaginary", "admin1")

    def test_all_valid_transitions(self) -> None:
        """Verify all declared transitions work."""
        for from_status, to_list in ADMIN_STATUS_TRANSITIONS.items():
            for to_status in to_list:
                users = [
                    {
                        "user_id": "u1",
                        "status": from_status,
                        "email": "a@b.com",
                    }
                ]
                svc = _make_service(users=users)
                result = svc.change_user_status(
                    "u1", to_status, "admin1"
                )
                assert result["new_status"] == to_status

    def test_status_change_logs_action(self) -> None:
        users = [{"user_id": "u1", "status": "active", "email": "a@b.com"}]
        svc = _make_service(users=users)
        svc.suspend_user("u1", "admin1", "test reason")
        svc.action_log_repo.create.assert_called_once()
        call_data = svc.action_log_repo.create.call_args
        assert "status_change" in str(call_data)


# ── Point Adjustment Tests ───────────────────────────────────────────


class TestAdjustPoints:
    """Test manual point adjustments."""

    def test_add_points(self) -> None:
        users = [
            {
                "user_id": "u1",
                "point_balance": 500,
                "email": "a@b.com",
                "status": "active",
            }
        ]
        svc = _make_service(users=users)
        result = svc.adjust_points("u1", 100, "Bonus", "admin1")
        assert result["old_balance"] == 500
        assert result["new_balance"] == 600
        assert result["amount"] == 100
        svc.transaction_repo.create.assert_called_once()

    def test_deduct_points(self) -> None:
        users = [
            {
                "user_id": "u1",
                "point_balance": 500,
                "email": "a@b.com",
                "status": "active",
            }
        ]
        svc = _make_service(users=users)
        result = svc.adjust_points("u1", -200, "Correction", "admin1")
        assert result["new_balance"] == 300

    def test_deduct_below_zero_clamps(self) -> None:
        users = [
            {
                "user_id": "u1",
                "point_balance": 100,
                "email": "a@b.com",
                "status": "active",
            }
        ]
        svc = _make_service(users=users)
        result = svc.adjust_points("u1", -500, "Major correction", "admin1")
        assert result["new_balance"] == 0

    def test_reason_required(self) -> None:
        users = [{"user_id": "u1", "point_balance": 100, "status": "active"}]
        svc = _make_service(users=users)
        with pytest.raises(AdminUserError, match="Reason is required"):
            svc.adjust_points("u1", 100, "", "admin1")

    def test_user_not_found(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="User not found"):
            svc.adjust_points("u999", 100, "Bonus", "admin1")

    def test_logs_action(self) -> None:
        users = [
            {
                "user_id": "u1",
                "point_balance": 500,
                "email": "a@b.com",
                "status": "active",
            }
        ]
        svc = _make_service(users=users)
        svc.adjust_points("u1", 100, "Good behavior", "admin1")
        svc.action_log_repo.create.assert_called_once()

    def test_updates_user_balance(self) -> None:
        users = [
            {
                "user_id": "u1",
                "point_balance": 500,
                "email": "a@b.com",
                "status": "active",
            }
        ]
        svc = _make_service(users=users)
        svc.adjust_points("u1", 100, "Bonus", "admin1")
        update_call = svc.user_repo.update.call_args
        data = update_call[1].get("data", update_call[0][1] if len(update_call[0]) > 1 else {})
        assert data["point_balance"] == 600


# ── Action Log Tests ─────────────────────────────────────────────────


class TestActionLog:
    """Test admin action log retrieval."""

    def test_get_action_log_empty(self) -> None:
        svc = _make_service()
        svc.action_log_repo.find_all.return_value = []
        svc.action_log_repo.count.return_value = 0
        result = svc.get_action_log()
        assert result["items"] == []
        assert result["pagination"]["total_items"] == 0

    def test_get_action_log_with_filters(self) -> None:
        svc = _make_service()
        svc.action_log_repo.find_all.return_value = [
            {"log_id": "l1", "action_type": "status_change"}
        ]
        svc.action_log_repo.count.return_value = 1
        result = svc.get_action_log(
            admin_id="admin1", action_type="status_change"
        )
        assert result["pagination"]["total_items"] == 1

    def test_get_action_log_by_target(self) -> None:
        svc = _make_service()
        svc.action_log_repo.find_all.return_value = []
        svc.action_log_repo.count.return_value = 0
        result = svc.get_action_log(target_user_id="u1")
        assert result["items"] == []


# ── User Detail Tests ────────────────────────────────────────────────


class TestUserDetail:
    """Test detailed user info retrieval."""

    def test_get_user_detail(self) -> None:
        users = [
            {
                "user_id": "u1",
                "email": "a@b.com",
                "status": "active",
                "point_balance": 500,
            }
        ]
        profiles = [
            {"user_id": "u1", "display_name": "John", "tier_code": "M-18-29-BEG"}
        ]
        svc = _make_service(users=users, profiles=profiles)
        svc.transaction_repo.find_all.return_value = []
        result = svc.get_user_detail("u1")
        assert result["email"] == "a@b.com"
        assert result["profile"]["display_name"] == "John"
        assert result["recent_transactions"] == []

    def test_get_user_detail_not_found(self) -> None:
        svc = _make_service()
        with pytest.raises(AdminUserError, match="User not found"):
            svc.get_user_detail("u999")

    def test_get_user_detail_no_profile(self) -> None:
        users = [{"user_id": "u1", "email": "a@b.com", "status": "active"}]
        svc = _make_service(users=users)
        svc.transaction_repo.find_all.return_value = []
        result = svc.get_user_detail("u1")
        assert "profile" not in result
