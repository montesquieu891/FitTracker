"""Drawing worker — automated drawing lifecycle management.

Periodically checks for drawings that need:
  - Ticket sales closed (T-5 minutes before drawing_time)
  - Drawing executed (at drawing_time for closed drawings)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class DrawingWorkerResult:
    """Result of a drawing worker run."""

    def __init__(self) -> None:
        self.sales_closed: list[str] = []
        self.drawings_executed: list[str] = []
        self.errors: list[str] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sales_closed": self.sales_closed,
            "drawings_executed": self.drawings_executed,
            "errors": self.errors,
            "success": self.success,
        }


class DrawingWorker:
    """Automated drawing lifecycle worker.

    Run periodically (e.g. every minute) to:
      1. Close ticket sales for drawings at T-5 minutes
      2. Execute drawings that are past their drawing_time
    """

    def __init__(
        self,
        drawing_service: Any,
        drawing_executor: Any,
    ) -> None:
        self.drawing_service = drawing_service
        self.drawing_executor = drawing_executor

    def run(self, now: datetime | None = None) -> DrawingWorkerResult:
        """Execute one cycle of the drawing worker."""
        if now is None:
            now = datetime.now(tz=UTC)

        result = DrawingWorkerResult()

        # Step 1: Close ticket sales for open drawings approaching T-5
        self._close_ticket_sales(now, result)

        # Step 2: Execute closed drawings that are past drawing_time
        self._execute_ready_drawings(now, result)

        return result

    def _close_ticket_sales(self, now: datetime, result: DrawingWorkerResult) -> None:
        """Auto-close ticket sales for drawings within 5 minutes."""
        try:
            open_drawings = self.drawing_service.drawing_repo.find_by_field("status", "open")
        except Exception as e:
            result.errors.append(f"Failed to fetch open drawings: {e}")
            return

        for drawing in open_drawings:
            drawing_id = drawing.get("drawing_id", "")
            if not drawing_id:
                continue

            try:
                should_close = self.drawing_service.check_sales_should_close(drawing_id, now)
                if should_close:
                    self.drawing_service.close_drawing(drawing_id)
                    result.sales_closed.append(drawing_id)
                    logger.info("Auto-closed ticket sales for %s", drawing_id)
            except Exception as e:
                result.errors.append(f"Failed to close sales for {drawing_id}: {e}")

    def _execute_ready_drawings(self, now: datetime, result: DrawingWorkerResult) -> None:
        """Auto-execute drawings that are past their drawing_time."""
        try:
            closed_drawings = self.drawing_service.drawing_repo.find_by_field("status", "closed")
        except Exception as e:
            result.errors.append(f"Failed to fetch closed drawings: {e}")
            return

        for drawing in closed_drawings:
            drawing_id = drawing.get("drawing_id", "")
            if not drawing_id:
                continue

            try:
                is_ready = self.drawing_service.check_drawing_ready(drawing_id, now)
                if is_ready:
                    self.drawing_executor.execute(drawing_id)
                    result.drawings_executed.append(drawing_id)
                    logger.info("Auto-executed drawing %s", drawing_id)
            except Exception as e:
                result.errors.append(f"Failed to execute drawing {drawing_id}: {e}")
