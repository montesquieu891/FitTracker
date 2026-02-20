"""Notification service — in-app notifications and email dispatch.

Manages creation, read/unread tracking, and email dispatch of
notifications. Uses console output in dev, pluggable for production.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised on notification operation failures."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Notification types for categorization
NOTIFICATION_TYPES = [
    "winner_selected",
    "fulfillment_update",
    "account_status_change",
    "point_adjustment",
    "verification",
    "password_reset",
    "general",
]

# Email template definitions
EMAIL_TEMPLATES: dict[str, dict[str, str]] = {
    "verification": {
        "subject": "Verify your FitTrack account",
        "body": (
            "Hi {display_name},\n\n"
            "Click the link below to verify your email:\n"
            "{verification_link}\n\n"
            "This link expires in 24 hours.\n\n"
            "— The FitTrack Team"
        ),
    },
    "password_reset": {
        "subject": "Reset your FitTrack password",
        "body": (
            "Hi {display_name},\n\n"
            "Click the link below to reset your password:\n"
            "{reset_link}\n\n"
            "This link expires in 1 hour.\n\n"
            "— The FitTrack Team"
        ),
    },
    "winner_notification": {
        "subject": "You won a prize on FitTrack!",
        "body": (
            "Congratulations {display_name}!\n\n"
            "You won: {prize_name}\n"
            "Drawing: {drawing_name}\n\n"
            "Please log in and confirm your shipping address "
            "within 14 days to claim your prize.\n\n"
            "— The FitTrack Team"
        ),
    },
    "fulfillment_shipped": {
        "subject": "Your FitTrack prize has shipped!",
        "body": (
            "Hi {display_name},\n\n"
            "Your prize ({prize_name}) has been shipped!\n"
            "Carrier: {carrier}\n"
            "Tracking: {tracking_number}\n\n"
            "— The FitTrack Team"
        ),
    },
    "fulfillment_delivered": {
        "subject": "Your FitTrack prize was delivered!",
        "body": (
            "Hi {display_name},\n\n"
            "Your prize ({prize_name}) has been delivered. "
            "Enjoy!\n\n"
            "— The FitTrack Team"
        ),
    },
    "account_suspended": {
        "subject": "Your FitTrack account has been suspended",
        "body": (
            "Hi {display_name},\n\n"
            "Your account has been suspended.\n"
            "Reason: {reason}\n\n"
            "If you believe this is an error, please contact "
            "support.\n\n"
            "— The FitTrack Team"
        ),
    },
    "account_activated": {
        "subject": "Your FitTrack account has been activated",
        "body": (
            "Hi {display_name},\n\n"
            "Your account is now active! You can log in and "
            "start tracking your fitness activities.\n\n"
            "— The FitTrack Team"
        ),
    },
    "point_adjustment": {
        "subject": "FitTrack point balance update",
        "body": (
            "Hi {display_name},\n\n"
            "Your point balance has been adjusted by {amount} "
            "points.\n"
            "Reason: {reason}\n"
            "New balance: {new_balance}\n\n"
            "— The FitTrack Team"
        ),
    },
}


class NotificationService:
    """Service for managing notifications and email dispatch."""

    def __init__(
        self,
        notification_repo: Any,
        email_service: Any | None = None,
        dev_mode: bool = True,
    ) -> None:
        self.notification_repo = notification_repo
        self.email_service = email_service
        self.dev_mode = dev_mode

    # ── Create Notifications ─────────────────────────────────────

    def create_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        *,
        metadata: dict[str, Any] | None = None,
        send_email: bool = False,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Create an in-app notification.

        Optionally sends email notification as well.
        """
        if notification_type not in NOTIFICATION_TYPES:
            raise NotificationError(
                f"Invalid type: {notification_type}. Valid: {NOTIFICATION_TYPES}",
                400,
            )

        notification_id = uuid.uuid4().hex
        now = datetime.now(tz=UTC).isoformat()

        data = {
            "user_id": user_id,
            "notification_type": notification_type,
            "title": title,
            "message": message,
            "metadata": str(metadata) if metadata else "",
            "is_read": 0,
            "email_sent": 0,
            "created_at": now,
        }

        self.notification_repo.create(data=data, new_id=notification_id)

        result = {"notification_id": notification_id, **data}

        # Send email if requested
        if send_email and email:
            self._dispatch_email(
                to=email,
                subject=title,
                body=message,
            )
            self.notification_repo.update(notification_id, data={"email_sent": 1})
            result["email_sent"] = 1

        logger.info(
            "Created notification %s for user %s: %s",
            notification_id,
            user_id,
            title,
        )

        return result

    # ── Notification Triggers ────────────────────────────────────

    def notify_winner(
        self,
        user_id: str,
        email: str,
        prize_name: str,
        drawing_name: str,
        display_name: str = "FitTrack User",
    ) -> dict[str, Any]:
        """Notify a user that they won a prize."""
        template = EMAIL_TEMPLATES["winner_notification"]
        body = template["body"].format(
            display_name=display_name,
            prize_name=prize_name,
            drawing_name=drawing_name,
        )
        return self.create_notification(
            user_id=user_id,
            notification_type="winner_selected",
            title=template["subject"],
            message=body,
            metadata={
                "prize_name": prize_name,
                "drawing_name": drawing_name,
            },
            send_email=True,
            email=email,
        )

    def notify_fulfillment_update(
        self,
        user_id: str,
        email: str,
        status: str,
        prize_name: str = "",
        display_name: str = "FitTrack User",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Notify user of fulfillment status change."""
        template_key = f"fulfillment_{status}"
        if template_key in EMAIL_TEMPLATES:
            template = EMAIL_TEMPLATES[template_key]
            body = template["body"].format(
                display_name=display_name,
                prize_name=prize_name,
                **kwargs,
            )
            title = template["subject"]
        else:
            title = f"Prize fulfillment update: {status}"
            body = f"Your prize fulfillment status has been updated to: {status}"

        return self.create_notification(
            user_id=user_id,
            notification_type="fulfillment_update",
            title=title,
            message=body,
            metadata={"status": status, "prize_name": prize_name},
            send_email=True,
            email=email,
        )

    def notify_account_status_change(
        self,
        user_id: str,
        email: str,
        new_status: str,
        reason: str = "",
        display_name: str = "FitTrack User",
    ) -> dict[str, Any]:
        """Notify user of account status change."""
        if new_status == "suspended":
            template = EMAIL_TEMPLATES["account_suspended"]
            body = template["body"].format(display_name=display_name, reason=reason or "N/A")
            title = template["subject"]
        elif new_status == "active":
            template = EMAIL_TEMPLATES["account_activated"]
            body = template["body"].format(display_name=display_name)
            title = template["subject"]
        else:
            title = f"Account status update: {new_status}"
            body = f"Your account status has been changed to: {new_status}"

        return self.create_notification(
            user_id=user_id,
            notification_type="account_status_change",
            title=title,
            message=body,
            metadata={
                "new_status": new_status,
                "reason": reason,
            },
            send_email=True,
            email=email,
        )

    def notify_point_adjustment(
        self,
        user_id: str,
        email: str,
        amount: int,
        new_balance: int,
        reason: str,
        display_name: str = "FitTrack User",
    ) -> dict[str, Any]:
        """Notify user of point balance adjustment."""
        template = EMAIL_TEMPLATES["point_adjustment"]
        body = template["body"].format(
            display_name=display_name,
            amount=f"{amount:+d}",
            new_balance=new_balance,
            reason=reason,
        )
        return self.create_notification(
            user_id=user_id,
            notification_type="point_adjustment",
            title=template["subject"],
            message=body,
            metadata={
                "amount": amount,
                "new_balance": new_balance,
                "reason": reason,
            },
            send_email=True,
            email=email,
        )

    # ── Read/Unread Tracking ─────────────────────────────────────

    def get_user_notifications(
        self,
        user_id: str,
        *,
        is_read: bool | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """Get paginated notifications for a user."""
        filters: dict[str, Any] = {"user_id": user_id}
        if is_read is not None:
            filters["is_read"] = 1 if is_read else 0

        offset = (page - 1) * limit
        items = self.notification_repo.find_all(limit=limit, offset=offset, filters=filters)
        total = self.notification_repo.count(filters=filters)
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

    def mark_as_read(self, notification_id: str, user_id: str) -> dict[str, Any]:
        """Mark a notification as read."""
        notification = self.notification_repo.find_by_id(notification_id)
        if not notification:
            raise NotificationError("Notification not found", 404)

        if notification.get("user_id") != user_id:
            raise NotificationError("Not authorized to access this notification", 403)

        if notification.get("is_read") == 1:
            return {"notification_id": notification_id, "already_read": True}

        now = datetime.now(tz=UTC).isoformat()
        self.notification_repo.update(notification_id, data={"is_read": 1, "read_at": now})

        return {
            "notification_id": notification_id,
            "is_read": True,
            "read_at": now,
        }

    def get_unread_count(self, user_id: str) -> int:
        """Get the count of unread notifications for a user."""
        return int(self.notification_repo.count(filters={"user_id": user_id, "is_read": 0}))

    def get_notification(self, notification_id: str) -> dict[str, Any]:
        """Get a single notification by ID."""
        notification = self.notification_repo.find_by_id(notification_id)
        if not notification:
            raise NotificationError("Notification not found", 404)
        result: dict[str, Any] = notification
        return result

    # ── Email Dispatch ───────────────────────────────────────────

    def _dispatch_email(
        self,
        to: str,
        subject: str,
        body: str,
    ) -> None:
        """Dispatch email (console in dev, real provider in prod)."""
        if self.email_service:
            self.email_service._send(to=to, subject=subject, body=body)
        elif self.dev_mode:
            logger.info(
                "[DEV EMAIL] To: %s | Subject: %s | Body: %s",
                to,
                subject,
                body[:200],
            )
        # Silently skip if no email service configured

    @staticmethod
    def render_template(template_key: str, **kwargs: Any) -> dict[str, str]:
        """Render an email template with the given variables."""
        if template_key not in EMAIL_TEMPLATES:
            raise NotificationError(
                f"Unknown template: {template_key}. Valid: {list(EMAIL_TEMPLATES.keys())}",
                400,
            )
        template = EMAIL_TEMPLATES[template_key]
        try:
            subject = template["subject"].format(**kwargs)
            body = template["body"].format(**kwargs)
        except KeyError as e:
            raise NotificationError(f"Missing template variable: {e}", 400) from e
        return {"subject": subject, "body": body}
