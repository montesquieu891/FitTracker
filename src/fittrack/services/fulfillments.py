"""Fulfillment service — prize fulfillment state machine.

Manages the lifecycle of prize delivery:
  pending → winner_notified → address_confirmed → shipped → delivered

With alternative paths:
  address_invalid → address_confirmed (recovery)
  any active state → forfeited (after 14-day timeout)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.core.constants import FULFILLMENT_STATUSES

logger = logging.getLogger(__name__)

# ── Constants ───────────────────────────────────────────────────────

ADDRESS_CONFIRM_WARNING_DAYS = 7
ADDRESS_CONFIRM_FORFEIT_DAYS = 14


# ── Valid state transitions ─────────────────────────────────────────

FULFILLMENT_TRANSITIONS: dict[str, list[str]] = {
    "pending": ["winner_notified", "forfeited"],
    "winner_notified": ["address_confirmed", "address_invalid", "forfeited"],
    "address_confirmed": ["shipped", "forfeited"],
    "address_invalid": ["address_confirmed", "forfeited"],
    "shipped": ["delivered", "forfeited"],
    "delivered": [],  # Terminal
    "forfeited": [],  # Terminal
}


class FulfillmentError(Exception):
    """Fulfillment service error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class FulfillmentService:
    """Manages prize fulfillment lifecycle and shipping."""

    def __init__(self, fulfillment_repo: Any) -> None:
        self.fulfillment_repo = fulfillment_repo

    # ── State transitions ───────────────────────────────────────────

    def transition_status(
        self,
        fulfillment_id: str,
        new_status: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Transition a fulfillment to a new status with validation."""
        if new_status not in FULFILLMENT_STATUSES:
            raise FulfillmentError(f"Invalid status: {new_status}")

        fulfillment = self.fulfillment_repo.find_by_id(fulfillment_id)
        if fulfillment is None:
            raise FulfillmentError("Fulfillment not found", status_code=404)

        current = fulfillment.get("status", "pending")
        allowed = FULFILLMENT_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            raise FulfillmentError(
                f"Cannot transition from '{current}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        now = datetime.now(tz=UTC).isoformat()
        update_data: dict[str, Any] = {"status": new_status}

        # Set relevant timestamps
        if new_status == "winner_notified":
            update_data["notified_at"] = now
        elif new_status == "address_confirmed":
            update_data["address_confirmed_at"] = now
            if "shipping_address" in kwargs:
                update_data["shipping_address"] = kwargs["shipping_address"]
        elif new_status == "shipped":
            update_data["shipped_at"] = now
            if "tracking_number" in kwargs:
                update_data["tracking_number"] = kwargs["tracking_number"]
            if "carrier" in kwargs:
                update_data["carrier"] = kwargs["carrier"]
        elif new_status == "delivered":
            update_data["delivered_at"] = now
        elif new_status == "forfeited":
            update_data["forfeit_at"] = now

        if "notes" in kwargs:
            update_data["notes"] = kwargs["notes"]

        self.fulfillment_repo.update(fulfillment_id, data=update_data)
        fulfillment.update(update_data)
        return fulfillment

    # ── Convenience methods ─────────────────────────────────────────

    def notify_winner(self, fulfillment_id: str) -> dict[str, Any]:
        """Mark winner as notified."""
        return self.transition_status(fulfillment_id, "winner_notified")

    def confirm_address(
        self,
        fulfillment_id: str,
        shipping_address: dict[str, Any],
    ) -> dict[str, Any]:
        """Winner confirms their shipping address."""
        if not shipping_address:
            raise FulfillmentError("Shipping address is required")

        required = ["street", "city", "state", "zip_code"]
        missing = [f for f in required if not shipping_address.get(f)]
        if missing:
            raise FulfillmentError(
                f"Missing address fields: {', '.join(missing)}"
            )

        return self.transition_status(
            fulfillment_id,
            "address_confirmed",
            shipping_address=shipping_address,
        )

    def mark_address_invalid(self, fulfillment_id: str) -> dict[str, Any]:
        """Admin marks address as invalid — winner can resubmit."""
        return self.transition_status(fulfillment_id, "address_invalid")

    def ship_prize(
        self,
        fulfillment_id: str,
        *,
        carrier: str,
        tracking_number: str,
    ) -> dict[str, Any]:
        """Admin marks prize as shipped with tracking info."""
        if not carrier:
            raise FulfillmentError("Carrier is required")
        if not tracking_number:
            raise FulfillmentError("Tracking number is required")

        return self.transition_status(
            fulfillment_id,
            "shipped",
            carrier=carrier,
            tracking_number=tracking_number,
        )

    def mark_delivered(self, fulfillment_id: str) -> dict[str, Any]:
        """Admin marks prize as delivered."""
        return self.transition_status(fulfillment_id, "delivered")

    def forfeit(self, fulfillment_id: str, reason: str = "") -> dict[str, Any]:
        """Forfeit a prize (timeout or winner request)."""
        return self.transition_status(
            fulfillment_id, "forfeited", notes=reason or "Forfeited"
        )

    # ── Queries ─────────────────────────────────────────────────────

    def get_fulfillment(self, fulfillment_id: str) -> dict[str, Any]:
        """Get a fulfillment by ID."""
        f = self.fulfillment_repo.find_by_id(fulfillment_id)
        if f is None:
            raise FulfillmentError("Fulfillment not found", status_code=404)
        return f

    def list_fulfillments(
        self,
        *,
        user_id: str | None = None,
        status: str | None = None,
        drawing_id: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List fulfillments with optional filters."""
        filters: dict[str, Any] = {}
        if user_id:
            filters["user_id"] = user_id
        if status:
            filters["status"] = status
        if drawing_id:
            filters["drawing_id"] = drawing_id

        total = self.fulfillment_repo.count(filters=filters)
        offset = (page - 1) * limit
        items = self.fulfillment_repo.find_all(
            limit=limit, offset=offset, filters=filters
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

    # ── Timeout checks ──────────────────────────────────────────────

    def check_confirmation_warning(
        self,
        fulfillment_id: str,
        now: datetime | None = None,
    ) -> bool:
        """Check if a 7-day warning should be sent to winner."""
        if now is None:
            now = datetime.now(tz=UTC)

        f = self.fulfillment_repo.find_by_id(fulfillment_id)
        if f is None or f.get("status") != "winner_notified":
            return False

        notified_at = f.get("notified_at")
        if notified_at is None:
            return False

        if isinstance(notified_at, str):
            try:
                notified_at = datetime.fromisoformat(notified_at)
            except ValueError:
                return False

        if notified_at.tzinfo is None:
            notified_at = notified_at.replace(tzinfo=UTC)

        warning_deadline = notified_at + timedelta(days=ADDRESS_CONFIRM_WARNING_DAYS)
        return now >= warning_deadline

    def check_forfeit_timeout(
        self,
        fulfillment_id: str,
        now: datetime | None = None,
    ) -> bool:
        """Check if a fulfillment should be forfeited (14-day timeout)."""
        if now is None:
            now = datetime.now(tz=UTC)

        f = self.fulfillment_repo.find_by_id(fulfillment_id)
        if f is None:
            return False

        # Only forfeit from pending states (not shipped/delivered)
        status = f.get("status", "pending")
        if status in ("shipped", "delivered", "forfeited"):
            return False

        notified_at = f.get("notified_at")
        if notified_at is None:
            # Not yet notified → can't forfeit
            return False

        if isinstance(notified_at, str):
            try:
                notified_at = datetime.fromisoformat(notified_at)
            except ValueError:
                return False

        if notified_at.tzinfo is None:
            notified_at = notified_at.replace(tzinfo=UTC)

        forfeit_deadline = notified_at + timedelta(days=ADDRESS_CONFIRM_FORFEIT_DAYS)
        return now >= forfeit_deadline

    def process_timeouts(
        self, now: datetime | None = None
    ) -> dict[str, Any]:
        """Process all fulfillments for warnings and forfeitures."""
        if now is None:
            now = datetime.now(tz=UTC)

        # Get active fulfillments (not delivered/forfeited)
        active_statuses = [
            "pending", "winner_notified", "address_confirmed", "address_invalid"
        ]
        warnings_sent = 0
        forfeited_count = 0

        for status in active_statuses:
            items = self.fulfillment_repo.find_all(
                limit=1000, offset=0, filters={"status": status}
            )
            for item in items:
                fid = item.get("fulfillment_id", "")
                if not fid:
                    continue

                if self.check_forfeit_timeout(fid, now):
                    try:
                        self.forfeit(fid, reason="14-day confirmation timeout")
                        forfeited_count += 1
                    except FulfillmentError:
                        pass
                elif self.check_confirmation_warning(fid, now):
                    warnings_sent += 1

        return {
            "warnings_sent": warnings_sent,
            "forfeited": forfeited_count,
        }
