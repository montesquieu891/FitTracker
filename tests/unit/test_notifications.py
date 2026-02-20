"""Tests for notification service — creation, dispatch, read/unread."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from fittrack.services.notifications import (
    EMAIL_TEMPLATES,
    NOTIFICATION_TYPES,
    NotificationError,
    NotificationService,
)

# ── Helpers ──────────────────────────────────────────────────────────


def _make_service(
    *,
    notifications: list[dict[str, Any]] | None = None,
    email_service: Any | None = None,
) -> NotificationService:
    """Create a NotificationService with mock repo."""
    repo = MagicMock()

    if notifications:
        repo.find_by_id.side_effect = lambda nid: next(
            (n for n in notifications if n.get("notification_id") == nid),
            None,
        )
        repo.find_all.return_value = notifications
        repo.count.return_value = len(notifications)
    else:
        repo.find_by_id.return_value = None
        repo.find_all.return_value = []
        repo.count.return_value = 0

    return NotificationService(
        notification_repo=repo,
        email_service=email_service,
        dev_mode=True,
    )


# ── Create Notification Tests ────────────────────────────────────────


class TestCreateNotification:
    """Test notification creation."""

    def test_create_basic(self) -> None:
        svc = _make_service()
        result = svc.create_notification(
            user_id="u1",
            notification_type="general",
            title="Hello",
            message="Test message",
        )
        assert result["notification_id"]
        assert result["user_id"] == "u1"
        assert result["title"] == "Hello"
        assert result["is_read"] == 0
        svc.notification_repo.create.assert_called_once()

    def test_create_with_email(self) -> None:
        email_svc = MagicMock()
        svc = _make_service(email_service=email_svc)
        result = svc.create_notification(
            user_id="u1",
            notification_type="general",
            title="Test",
            message="Body",
            send_email=True,
            email="a@b.com",
        )
        assert result["email_sent"] == 1
        email_svc._send.assert_called_once()

    def test_create_without_email_flag(self) -> None:
        email_svc = MagicMock()
        svc = _make_service(email_service=email_svc)
        svc.create_notification(
            user_id="u1",
            notification_type="general",
            title="Test",
            message="Body",
        )
        email_svc._send.assert_not_called()

    def test_invalid_type(self) -> None:
        svc = _make_service()
        with pytest.raises(NotificationError, match="Invalid type"):
            svc.create_notification(
                user_id="u1",
                notification_type="unknown_type",
                title="Test",
                message="Body",
            )

    def test_with_metadata(self) -> None:
        svc = _make_service()
        result = svc.create_notification(
            user_id="u1",
            notification_type="general",
            title="Test",
            message="Body",
            metadata={"key": "value"},
        )
        assert "metadata" in result


# ── Notification Triggers Tests ──────────────────────────────────────


class TestNotificationTriggers:
    """Test specific notification trigger methods."""

    def test_notify_winner(self) -> None:
        svc = _make_service()
        result = svc.notify_winner(
            user_id="u1",
            email="a@b.com",
            prize_name="iPhone 16",
            drawing_name="Daily Draw",
        )
        assert result["notification_type"] == "winner_selected"
        assert "iPhone 16" in result["message"]
        assert "Daily Draw" in result["message"]

    def test_notify_winner_with_display_name(self) -> None:
        svc = _make_service()
        result = svc.notify_winner(
            user_id="u1",
            email="a@b.com",
            prize_name="Prize",
            drawing_name="Draw",
            display_name="John",
        )
        assert "John" in result["message"]

    def test_notify_fulfillment_shipped(self) -> None:
        svc = _make_service()
        result = svc.notify_fulfillment_update(
            user_id="u1",
            email="a@b.com",
            status="shipped",
            prize_name="Widget",
            carrier="UPS",
            tracking_number="1Z999AA",
        )
        assert result["notification_type"] == "fulfillment_update"
        assert "shipped" in result["title"].lower()

    def test_notify_fulfillment_delivered(self) -> None:
        svc = _make_service()
        result = svc.notify_fulfillment_update(
            user_id="u1",
            email="a@b.com",
            status="delivered",
            prize_name="Widget",
        )
        assert "delivered" in result["title"].lower()

    def test_notify_fulfillment_unknown_status(self) -> None:
        svc = _make_service()
        result = svc.notify_fulfillment_update(
            user_id="u1",
            email="a@b.com",
            status="pending",
            prize_name="Widget",
        )
        assert result["notification_type"] == "fulfillment_update"

    def test_notify_account_suspended(self) -> None:
        svc = _make_service()
        result = svc.notify_account_status_change(
            user_id="u1",
            email="a@b.com",
            new_status="suspended",
            reason="Violation",
        )
        assert result["notification_type"] == "account_status_change"
        assert "suspended" in result["title"].lower()

    def test_notify_account_activated(self) -> None:
        svc = _make_service()
        result = svc.notify_account_status_change(
            user_id="u1",
            email="a@b.com",
            new_status="active",
        )
        assert "activated" in result["title"].lower()

    def test_notify_account_other_status(self) -> None:
        svc = _make_service()
        result = svc.notify_account_status_change(
            user_id="u1",
            email="a@b.com",
            new_status="banned",
        )
        assert "banned" in result["title"]

    def test_notify_point_adjustment(self) -> None:
        svc = _make_service()
        result = svc.notify_point_adjustment(
            user_id="u1",
            email="a@b.com",
            amount=500,
            new_balance=1500,
            reason="Bonus reward",
        )
        assert result["notification_type"] == "point_adjustment"
        assert "+500" in result["message"]
        assert "Bonus reward" in result["message"]

    def test_notify_point_deduction(self) -> None:
        svc = _make_service()
        result = svc.notify_point_adjustment(
            user_id="u1",
            email="a@b.com",
            amount=-200,
            new_balance=300,
            reason="Correction",
        )
        assert "-200" in result["message"]


# ── Read/Unread Tests ────────────────────────────────────────────────


class TestReadUnread:
    """Test read/unread tracking."""

    def test_mark_as_read(self) -> None:
        notifications = [
            {
                "notification_id": "n1",
                "user_id": "u1",
                "is_read": 0,
            }
        ]
        svc = _make_service(notifications=notifications)
        result = svc.mark_as_read("n1", "u1")
        assert result["is_read"] is True
        svc.notification_repo.update.assert_called_once()

    def test_mark_already_read(self) -> None:
        notifications = [
            {
                "notification_id": "n1",
                "user_id": "u1",
                "is_read": 1,
            }
        ]
        svc = _make_service(notifications=notifications)
        result = svc.mark_as_read("n1", "u1")
        assert result["already_read"] is True
        svc.notification_repo.update.assert_not_called()

    def test_mark_not_found(self) -> None:
        svc = _make_service()
        with pytest.raises(NotificationError, match="not found"):
            svc.mark_as_read("n999", "u1")

    def test_mark_wrong_user(self) -> None:
        notifications = [
            {
                "notification_id": "n1",
                "user_id": "u1",
                "is_read": 0,
            }
        ]
        svc = _make_service(notifications=notifications)
        with pytest.raises(NotificationError, match="Not authorized"):
            svc.mark_as_read("n1", "u2")

    def test_get_unread_count(self) -> None:
        svc = _make_service()
        svc.notification_repo.count.return_value = 5
        count = svc.get_unread_count("u1")
        assert count == 5

    def test_get_user_notifications(self) -> None:
        notifications = [
            {"notification_id": "n1", "user_id": "u1", "is_read": 0},
            {"notification_id": "n2", "user_id": "u1", "is_read": 1},
        ]
        svc = _make_service(notifications=notifications)
        result = svc.get_user_notifications("u1")
        assert result["pagination"]["total_items"] == 2

    def test_get_user_notifications_unread_only(self) -> None:
        svc = _make_service()
        svc.notification_repo.find_all.return_value = [{"notification_id": "n1", "is_read": 0}]
        svc.notification_repo.count.return_value = 1
        result = svc.get_user_notifications("u1", is_read=False)
        assert result["pagination"]["total_items"] == 1


# ── Email Template Tests ─────────────────────────────────────────────


class TestEmailTemplates:
    """Test email template rendering."""

    def test_render_verification(self) -> None:
        result = NotificationService.render_template(
            "verification",
            display_name="John",
            verification_link="https://example.com/verify",
        )
        assert "John" in result["body"]
        assert "verify" in result["body"].lower()

    def test_render_password_reset(self) -> None:
        result = NotificationService.render_template(
            "password_reset",
            display_name="Jane",
            reset_link="https://example.com/reset",
        )
        assert "Jane" in result["body"]
        assert "reset" in result["body"].lower()

    def test_render_winner_notification(self) -> None:
        result = NotificationService.render_template(
            "winner_notification",
            display_name="Bob",
            prize_name="iPhone",
            drawing_name="Daily Draw",
        )
        assert "Bob" in result["body"]
        assert "iPhone" in result["body"]

    def test_render_unknown_template(self) -> None:
        with pytest.raises(NotificationError, match="Unknown template"):
            NotificationService.render_template("nonexistent")

    def test_render_missing_variable(self) -> None:
        with pytest.raises(NotificationError, match="Missing template"):
            NotificationService.render_template("verification")

    def test_all_templates_have_subject_and_body(self) -> None:
        for key, template in EMAIL_TEMPLATES.items():
            assert "subject" in template, f"Template {key} missing subject"
            assert "body" in template, f"Template {key} missing body"


# ── Get Notification Tests ───────────────────────────────────────────


class TestGetNotification:
    """Test single notification retrieval."""

    def test_get_found(self) -> None:
        notifications = [{"notification_id": "n1", "user_id": "u1", "title": "Hi"}]
        svc = _make_service(notifications=notifications)
        result = svc.get_notification("n1")
        assert result["title"] == "Hi"

    def test_get_not_found(self) -> None:
        svc = _make_service()
        with pytest.raises(NotificationError, match="not found"):
            svc.get_notification("n999")


# ── Notification Types Completeness ──────────────────────────────────


class TestNotificationTypes:
    """Test notification type constants."""

    def test_all_types_valid(self) -> None:
        svc = _make_service()
        for ntype in NOTIFICATION_TYPES:
            result = svc.create_notification(
                user_id="u1",
                notification_type=ntype,
                title=f"Test {ntype}",
                message="body",
            )
            assert result["notification_type"] == ntype

    def test_types_match_constants(self) -> None:
        from fittrack.core.constants import (
            NOTIFICATION_TYPES as CONST_TYPES,
        )

        assert set(NOTIFICATION_TYPES) == set(CONST_TYPES)
