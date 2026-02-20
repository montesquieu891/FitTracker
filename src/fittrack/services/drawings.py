"""Drawing service — lifecycle management for sweepstakes drawings.

Manages the drawing lifecycle: draft → scheduled → open → closed → completed/cancelled.
Enforces business rules around ticket sales windows and eligibility.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.core.constants import (
    DRAWING_STATUSES,
    DRAWING_TICKET_COSTS,
    DRAWING_TYPES,
    TICKET_SALES_CLOSE_MINUTES_BEFORE,
)

logger = logging.getLogger(__name__)


class DrawingError(Exception):
    """Drawing service error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Valid state transitions ─────────────────────────────────────────

VALID_TRANSITIONS: dict[str, list[str]] = {
    "draft": ["scheduled", "cancelled"],
    "scheduled": ["open", "cancelled"],
    "open": ["closed", "cancelled"],
    "closed": ["completed", "cancelled"],
    "completed": [],  # Terminal
    "cancelled": [],  # Terminal
}


class DrawingService:
    """Orchestrates drawing lifecycle, validation, and queries."""

    def __init__(
        self,
        drawing_repo: Any,
        ticket_repo: Any,
        prize_repo: Any,
    ) -> None:
        self.drawing_repo = drawing_repo
        self.ticket_repo = ticket_repo
        self.prize_repo = prize_repo

    # ── Create ──────────────────────────────────────────────────────

    def create_drawing(
        self,
        *,
        drawing_type: str,
        name: str,
        description: str | None = None,
        ticket_cost_points: int | None = None,
        drawing_time: datetime | None = None,
        eligibility: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        """Create a new drawing in draft status."""
        if drawing_type not in DRAWING_TYPES:
            raise DrawingError(f"Invalid drawing type: {drawing_type}")

        # Default ticket cost from constants
        if ticket_cost_points is None:
            ticket_cost_points = DRAWING_TICKET_COSTS.get(drawing_type, 100)

        # Calculate ticket sales close time
        ticket_sales_close = None
        if drawing_time is not None:
            ticket_sales_close = drawing_time - timedelta(
                minutes=TICKET_SALES_CLOSE_MINUTES_BEFORE
            )

        from fittrack.repositories.base import BaseRepository

        drawing_id = BaseRepository._generate_id()

        data = {
            "drawing_type": drawing_type,
            "name": name,
            "description": description,
            "ticket_cost_points": ticket_cost_points,
            "drawing_time": drawing_time,
            "ticket_sales_close": ticket_sales_close,
            "eligibility": eligibility,
            "status": "draft",
            "total_tickets": 0,
            "created_by": created_by,
        }

        self.drawing_repo.create(data=data, new_id=drawing_id)

        return {"drawing_id": drawing_id, **data}

    # ── Lifecycle transitions ───────────────────────────────────────

    def transition_status(
        self, drawing_id: str, new_status: str
    ) -> dict[str, Any]:
        """Transition a drawing to a new status."""
        if new_status not in DRAWING_STATUSES:
            raise DrawingError(f"Invalid status: {new_status}")

        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            raise DrawingError("Drawing not found", status_code=404)

        current = drawing.get("status", "draft")
        allowed = VALID_TRANSITIONS.get(current, [])

        if new_status not in allowed:
            raise DrawingError(
                f"Cannot transition from '{current}' to '{new_status}'. "
                f"Allowed: {allowed}"
            )

        update_data: dict[str, Any] = {"status": new_status}
        if new_status == "completed":
            update_data["completed_at"] = datetime.now(tz=UTC).isoformat()

        self.drawing_repo.update(drawing_id, data=update_data)
        drawing.update(update_data)
        return drawing

    def schedule_drawing(self, drawing_id: str) -> dict[str, Any]:
        """Move drawing from draft to scheduled."""
        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            raise DrawingError("Drawing not found", status_code=404)
        if not drawing.get("drawing_time"):
            raise DrawingError("Cannot schedule without a drawing_time")
        return self.transition_status(drawing_id, "scheduled")

    def open_drawing(self, drawing_id: str) -> dict[str, Any]:
        """Move drawing from scheduled to open (ticket sales begin)."""
        return self.transition_status(drawing_id, "open")

    def close_drawing(self, drawing_id: str) -> dict[str, Any]:
        """Close ticket sales for a drawing."""
        return self.transition_status(drawing_id, "closed")

    def cancel_drawing(self, drawing_id: str) -> dict[str, Any]:
        """Cancel a drawing (from any non-terminal status)."""
        return self.transition_status(drawing_id, "cancelled")

    # ── Queries ─────────────────────────────────────────────────────

    def get_drawing(self, drawing_id: str) -> dict[str, Any]:
        """Get drawing with prize info."""
        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            raise DrawingError("Drawing not found", status_code=404)

        prizes = self.prize_repo.find_by_field("drawing_id", drawing_id)
        drawing["prizes"] = prizes
        drawing["total_tickets"] = self.ticket_repo.count_by_drawing(drawing_id)
        return drawing

    def list_drawings(
        self,
        *,
        drawing_type: str | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List drawings with optional filters and pagination."""
        filters: dict[str, Any] = {}
        if drawing_type:
            if drawing_type not in DRAWING_TYPES:
                raise DrawingError(f"Invalid drawing type filter: {drawing_type}")
            filters["drawing_type"] = drawing_type
        if status:
            if status not in DRAWING_STATUSES:
                raise DrawingError(f"Invalid status filter: {status}")
            filters["status"] = status

        total = self.drawing_repo.count(filters=filters)
        offset = (page - 1) * limit
        items = self.drawing_repo.find_all(limit=limit, offset=offset, filters=filters)
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

    def get_results(self, drawing_id: str) -> dict[str, Any]:
        """Get drawing results (only for completed drawings)."""
        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            raise DrawingError("Drawing not found", status_code=404)
        if drawing.get("status") != "completed":
            raise DrawingError(
                "Results only available for completed drawings",
                status_code=400,
            )

        tickets = self.ticket_repo.find_by_drawing(drawing_id)
        winners = [t for t in tickets if t.get("is_winner")]
        prizes = self.prize_repo.find_by_field("drawing_id", drawing_id)

        return {
            "drawing_id": drawing_id,
            "drawing": drawing,
            "total_tickets": len(tickets),
            "winners": winners,
            "prizes": prizes,
            "completed_at": drawing.get("completed_at"),
        }

    # ── Ticket sales window ─────────────────────────────────────────

    def is_ticket_sales_open(
        self, drawing_id: str, now: datetime | None = None
    ) -> bool:
        """Check if ticket sales are currently open for a drawing."""
        if now is None:
            now = datetime.now(tz=UTC)

        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None:
            return False

        if drawing.get("status") != "open":
            return False

        sales_close = drawing.get("ticket_sales_close")
        if sales_close is not None:
            if isinstance(sales_close, str):
                with contextlib.suppress(ValueError):
                    sales_close = datetime.fromisoformat(sales_close)
            if isinstance(sales_close, datetime):
                if sales_close.tzinfo is None:
                    sales_close = sales_close.replace(tzinfo=UTC)
                if now >= sales_close:
                    return False

        return True

    def check_sales_should_close(
        self, drawing_id: str, now: datetime | None = None
    ) -> bool:
        """Check if ticket sales should auto-close (T-5 minutes)."""
        if now is None:
            now = datetime.now(tz=UTC)

        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None or drawing.get("status") != "open":
            return False

        drawing_time = drawing.get("drawing_time")
        if drawing_time is None:
            return False

        if isinstance(drawing_time, str):
            try:
                drawing_time = datetime.fromisoformat(drawing_time)
            except ValueError:
                return False

        if isinstance(drawing_time, datetime):
            if drawing_time.tzinfo is None:
                drawing_time = drawing_time.replace(tzinfo=UTC)
            close_time = drawing_time - timedelta(
                minutes=TICKET_SALES_CLOSE_MINUTES_BEFORE
            )
            return now >= close_time

        return False

    def check_drawing_ready(
        self, drawing_id: str, now: datetime | None = None
    ) -> bool:
        """Check if a drawing is ready to execute (past drawing_time)."""
        if now is None:
            now = datetime.now(tz=UTC)

        drawing = self.drawing_repo.find_by_id(drawing_id)
        if drawing is None or drawing.get("status") != "closed":
            return False

        drawing_time = drawing.get("drawing_time")
        if drawing_time is None:
            return False

        if isinstance(drawing_time, str):
            try:
                drawing_time = datetime.fromisoformat(drawing_time)
            except ValueError:
                return False

        if isinstance(drawing_time, datetime):
            if drawing_time.tzinfo is None:
                drawing_time = drawing_time.replace(tzinfo=UTC)
            return now >= drawing_time

        return False
