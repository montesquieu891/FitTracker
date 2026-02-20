"""Tests for drawing service — lifecycle management."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fittrack.services.drawings import (
    VALID_TRANSITIONS,
    DrawingError,
    DrawingService,
)

# ── Mock repositories ───────────────────────────────────────────────


class MockDrawingRepo:
    def __init__(self, drawings: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for d in drawings or []:
            did = d.get("drawing_id", "")
            self._store[did] = dict(d)

    def find_by_id(self, drawing_id: str) -> dict[str, Any] | None:
        return self._store.get(drawing_id)

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [d for d in self._store.values() if d.get(field) == value]

    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        items = list(self._store.values())
        if filters:
            for k, v in filters.items():
                items = [i for i in items if i.get(k) == v]
        return items[offset : offset + limit]

    def count(self, filters: dict[str, Any] | None = None) -> int:
        items = list(self._store.values())
        if filters:
            for k, v in filters.items():
                items = [i for i in items if i.get(k) == v]
        return len(items)

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"drawing_id": new_id, **data}

    def update(self, drawing_id: str, data: dict[str, Any]) -> int:
        if drawing_id in self._store:
            self._store[drawing_id].update(data)
            return 1
        return 0

    def delete(self, drawing_id: str) -> int:
        if drawing_id in self._store:
            del self._store[drawing_id]
            return 1
        return 0


class MockTicketRepo:
    def __init__(self, tickets: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for t in tickets or []:
            self._store[t.get("ticket_id", "")] = dict(t)

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get("drawing_id") == drawing_id]

    def count_by_drawing(self, drawing_id: str) -> int:
        return len(self.find_by_drawing(drawing_id))

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get(field) == value]


class MockPrizeRepo:
    def __init__(self, prizes: list[dict[str, Any]] | None = None) -> None:
        self._store = {p.get("prize_id", ""): dict(p) for p in prizes or []}

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [p for p in self._store.values() if p.get(field) == value]


def _make_service(
    drawings: list[dict[str, Any]] | None = None,
    tickets: list[dict[str, Any]] | None = None,
    prizes: list[dict[str, Any]] | None = None,
) -> DrawingService:
    return DrawingService(
        drawing_repo=MockDrawingRepo(drawings),
        ticket_repo=MockTicketRepo(tickets),
        prize_repo=MockPrizeRepo(prizes),
    )


# ── Create drawing tests ───────────────────────────────────────────


class TestCreateDrawing:
    def test_create_daily_drawing(self):
        svc = _make_service()
        result = svc.create_drawing(
            drawing_type="daily",
            name="Daily Prize Draw",
            drawing_time=datetime(2026, 3, 1, 18, 0, tzinfo=UTC),
        )
        assert result["drawing_id"]
        assert result["drawing_type"] == "daily"
        assert result["name"] == "Daily Prize Draw"
        assert result["status"] == "draft"
        assert result["ticket_cost_points"] == 100  # Default from constants

    def test_create_weekly_drawing(self):
        svc = _make_service()
        result = svc.create_drawing(drawing_type="weekly", name="Weekly Draw")
        assert result["ticket_cost_points"] == 500

    def test_create_monthly_drawing(self):
        svc = _make_service()
        result = svc.create_drawing(drawing_type="monthly", name="Monthly Draw")
        assert result["ticket_cost_points"] == 2000

    def test_create_annual_drawing(self):
        svc = _make_service()
        result = svc.create_drawing(drawing_type="annual", name="Annual Draw")
        assert result["ticket_cost_points"] == 10000

    def test_create_custom_cost(self):
        svc = _make_service()
        result = svc.create_drawing(
            drawing_type="daily", name="Custom", ticket_cost_points=250
        )
        assert result["ticket_cost_points"] == 250

    def test_create_invalid_type_raises(self):
        svc = _make_service()
        with pytest.raises(DrawingError, match="Invalid drawing type"):
            svc.create_drawing(drawing_type="hourly", name="Bad")

    def test_create_sets_ticket_sales_close(self):
        svc = _make_service()
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        result = svc.create_drawing(
            drawing_type="daily", name="Test", drawing_time=draw_time
        )
        expected = draw_time - timedelta(minutes=5)
        assert result["ticket_sales_close"] == expected

    def test_create_no_draw_time(self):
        svc = _make_service()
        result = svc.create_drawing(drawing_type="daily", name="No Time")
        assert result["ticket_sales_close"] is None


# ── Lifecycle transition tests ──────────────────────────────────────


class TestDrawingLifecycle:
    def _make_drawing(
        self, status: str = "draft", **kwargs: Any
    ) -> dict[str, Any]:
        return {
            "drawing_id": "d1",
            "drawing_type": "daily",
            "name": "Test Draw",
            "status": status,
            "drawing_time": datetime(2026, 3, 1, 18, 0, tzinfo=UTC).isoformat(),
            **kwargs,
        }

    def test_draft_to_scheduled(self):
        d = self._make_drawing("draft")
        svc = _make_service(drawings=[d])
        result = svc.schedule_drawing("d1")
        assert result["status"] == "scheduled"

    def test_schedule_requires_drawing_time(self):
        d = self._make_drawing("draft")
        del d["drawing_time"]
        svc = _make_service(drawings=[d])
        with pytest.raises(DrawingError, match="Cannot schedule"):
            svc.schedule_drawing("d1")

    def test_scheduled_to_open(self):
        d = self._make_drawing("scheduled")
        svc = _make_service(drawings=[d])
        result = svc.open_drawing("d1")
        assert result["status"] == "open"

    def test_open_to_closed(self):
        d = self._make_drawing("open")
        svc = _make_service(drawings=[d])
        result = svc.close_drawing("d1")
        assert result["status"] == "closed"

    def test_cancel_from_any_active(self):
        for status in ["draft", "scheduled", "open", "closed"]:
            d = self._make_drawing(status)
            svc = _make_service(drawings=[d])
            result = svc.cancel_drawing("d1")
            assert result["status"] == "cancelled"

    def test_cannot_cancel_completed(self):
        d = self._make_drawing("completed")
        svc = _make_service(drawings=[d])
        with pytest.raises(DrawingError, match="Cannot transition"):
            svc.cancel_drawing("d1")

    def test_cannot_cancel_cancelled(self):
        d = self._make_drawing("cancelled")
        svc = _make_service(drawings=[d])
        with pytest.raises(DrawingError, match="Cannot transition"):
            svc.cancel_drawing("d1")

    def test_invalid_transition(self):
        d = self._make_drawing("draft")
        svc = _make_service(drawings=[d])
        with pytest.raises(DrawingError, match="Cannot transition"):
            svc.transition_status("d1", "completed")

    def test_transition_not_found(self):
        svc = _make_service()
        with pytest.raises(DrawingError, match="not found"):
            svc.transition_status("nonexistent", "open")

    def test_invalid_status_value(self):
        svc = _make_service()
        with pytest.raises(DrawingError, match="Invalid status"):
            svc.transition_status("d1", "bogus")

    def test_completed_sets_timestamp(self):
        d = self._make_drawing("closed")
        svc = _make_service(drawings=[d])
        result = svc.transition_status("d1", "completed")
        assert result["completed_at"] is not None


# ── Query tests ─────────────────────────────────────────────────────


class TestDrawingQueries:
    def test_get_drawing_with_prizes(self):
        d = {"drawing_id": "d1", "drawing_type": "daily", "name": "Test", "status": "open"}
        prizes = [{"prize_id": "p1", "drawing_id": "d1", "name": "Prize 1"}]
        svc = _make_service(drawings=[d], prizes=prizes)
        result = svc.get_drawing("d1")
        assert result["prizes"] == prizes
        assert result["total_tickets"] == 0

    def test_get_drawing_not_found(self):
        svc = _make_service()
        with pytest.raises(DrawingError, match="not found"):
            svc.get_drawing("nope")

    def test_list_drawings_all(self):
        drawings = [
            {"drawing_id": f"d{i}", "drawing_type": "daily", "name": f"D{i}", "status": "open"}
            for i in range(5)
        ]
        svc = _make_service(drawings=drawings)
        result = svc.list_drawings()
        assert result["pagination"]["total_items"] == 5

    def test_list_drawings_filter_type(self):
        drawings = [
            {"drawing_id": "d1", "drawing_type": "daily", "name": "D1", "status": "open"},
            {"drawing_id": "d2", "drawing_type": "weekly", "name": "D2", "status": "open"},
        ]
        svc = _make_service(drawings=drawings)
        result = svc.list_drawings(drawing_type="daily")
        assert result["pagination"]["total_items"] == 1

    def test_list_drawings_filter_status(self):
        drawings = [
            {"drawing_id": "d1", "drawing_type": "daily", "name": "D1", "status": "open"},
            {"drawing_id": "d2", "drawing_type": "daily", "name": "D2", "status": "closed"},
        ]
        svc = _make_service(drawings=drawings)
        result = svc.list_drawings(status="open")
        assert result["pagination"]["total_items"] == 1

    def test_list_drawings_invalid_type(self):
        svc = _make_service()
        with pytest.raises(DrawingError, match="Invalid drawing type"):
            svc.list_drawings(drawing_type="bogus")

    def test_list_drawings_pagination(self):
        drawings = [
            {"drawing_id": f"d{i}", "drawing_type": "daily", "name": f"D{i}", "status": "open"}
            for i in range(10)
        ]
        svc = _make_service(drawings=drawings)
        result = svc.list_drawings(page=2, limit=3)
        assert len(result["items"]) == 3
        assert result["pagination"]["total_pages"] == 4

    def test_get_results_completed(self):
        d = {"drawing_id": "d1", "drawing_type": "daily", "name": "D", "status": "completed"}
        tickets = [
            {"ticket_id": "t1", "drawing_id": "d1", "user_id": "u1", "is_winner": True},
            {"ticket_id": "t2", "drawing_id": "d1", "user_id": "u2", "is_winner": False},
        ]
        svc = _make_service(drawings=[d], tickets=tickets)
        result = svc.get_results("d1")
        assert result["total_tickets"] == 2
        assert len(result["winners"]) == 1

    def test_get_results_not_completed(self):
        d = {"drawing_id": "d1", "drawing_type": "daily", "name": "D", "status": "open"}
        svc = _make_service(drawings=[d])
        with pytest.raises(DrawingError, match="completed"):
            svc.get_results("d1")


# ── Ticket sales window tests ──────────────────────────────────────


class TestTicketSalesWindow:
    def test_sales_open_when_status_open(self):
        d = {
            "drawing_id": "d1",
            "status": "open",
            "ticket_sales_close": datetime(2026, 3, 1, 17, 55, tzinfo=UTC).isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        assert svc.is_ticket_sales_open("d1", now) is True

    def test_sales_closed_past_deadline(self):
        d = {
            "drawing_id": "d1",
            "status": "open",
            "ticket_sales_close": datetime(2026, 3, 1, 17, 55, tzinfo=UTC).isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 17, 56, tzinfo=UTC)
        assert svc.is_ticket_sales_open("d1", now) is False

    def test_sales_closed_when_not_open_status(self):
        d = {"drawing_id": "d1", "status": "draft"}
        svc = _make_service(drawings=[d])
        assert svc.is_ticket_sales_open("d1") is False

    def test_sales_closed_for_nonexistent(self):
        svc = _make_service()
        assert svc.is_ticket_sales_open("nope") is False

    def test_should_close_at_t_minus_5(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        d = {
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": draw_time.isoformat(),
        }
        svc = _make_service(drawings=[d])
        # T-5 minutes
        now = datetime(2026, 3, 1, 17, 55, tzinfo=UTC)
        assert svc.check_sales_should_close("d1", now) is True

    def test_should_not_close_before_t_minus_5(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        d = {
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": draw_time.isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 17, 50, tzinfo=UTC)
        assert svc.check_sales_should_close("d1", now) is False

    def test_drawing_ready_when_past_time(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        d = {
            "drawing_id": "d1",
            "status": "closed",
            "drawing_time": draw_time.isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 18, 1, tzinfo=UTC)
        assert svc.check_drawing_ready("d1", now) is True

    def test_drawing_not_ready_before_time(self):
        draw_time = datetime(2026, 3, 1, 18, 0, tzinfo=UTC)
        d = {
            "drawing_id": "d1",
            "status": "closed",
            "drawing_time": draw_time.isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 17, 59, tzinfo=UTC)
        assert svc.check_drawing_ready("d1", now) is False

    def test_drawing_not_ready_wrong_status(self):
        d = {
            "drawing_id": "d1",
            "status": "open",
            "drawing_time": datetime(2026, 3, 1, 18, 0, tzinfo=UTC).isoformat(),
        }
        svc = _make_service(drawings=[d])
        now = datetime(2026, 3, 1, 18, 1, tzinfo=UTC)
        assert svc.check_drawing_ready("d1", now) is False


# ── Valid transitions map tests ─────────────────────────────────────


class TestValidTransitions:
    def test_all_statuses_covered(self):
        from fittrack.core.constants import DRAWING_STATUSES

        for s in DRAWING_STATUSES:
            assert s in VALID_TRANSITIONS

    def test_terminal_states_have_no_transitions(self):
        assert VALID_TRANSITIONS["completed"] == []
        assert VALID_TRANSITIONS["cancelled"] == []

    def test_draft_can_schedule_or_cancel(self):
        assert set(VALID_TRANSITIONS["draft"]) == {"scheduled", "cancelled"}
