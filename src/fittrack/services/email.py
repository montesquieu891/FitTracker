"""Email service stub — console output in development, pluggable in production."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class EmailService:
    """Stub email service. In production, swap for SES/SendGrid."""

    def __init__(self, dev_mode: bool = True) -> None:
        self.dev_mode = dev_mode

    def send_verification(self, email: str, token: str) -> None:
        """Send email verification link."""
        link = f"https://fittrack.app/verify?token={token}"
        self._send(
            to=email,
            subject="Verify your FitTrack account",
            body=f"Click here to verify your email: {link}",
            metadata={"type": "verification", "token": token},
        )

    def send_password_reset(self, email: str, token: str) -> None:
        """Send password reset link."""
        link = f"https://fittrack.app/reset-password?token={token}"
        self._send(
            to=email,
            subject="Reset your FitTrack password",
            body=f"Click here to reset your password: {link}",
            metadata={"type": "password_reset", "token": token},
        )

    def send_prize_notification(self, email: str, prize_name: str) -> None:
        """Notify prize winner."""
        self._send(
            to=email,
            subject="🎉 You won a prize on FitTrack!",
            body=f"Congratulations! You won: {prize_name}. "
            "Log in to confirm your shipping address within 14 days.",
            metadata={"type": "prize_notification"},
        )

    def _send(
        self,
        to: str,
        subject: str,
        body: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Send email (console in dev, real provider in prod)."""
        if self.dev_mode:
            logger.info(
                "📧 [DEV EMAIL] To: %s | Subject: %s | Body: %s",
                to,
                subject,
                body[:200],
            )
        else:
            # Production: integrate SES/SendGrid here
            raise NotImplementedError("Production email provider not configured")
