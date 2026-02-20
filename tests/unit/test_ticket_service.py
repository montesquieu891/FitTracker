"""Tests for ticket service — purchase with atomic point deduction."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fittrack.services.tickets import TicketError, TicketService

# ── Mock repositories ───────────────────────────────────────────────


class MockTicketRepo:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"ticket_id": new_id, **data}

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get("drawing_id") == drawing_id]

    def update(self, ticket_id: str, data: dict[str, Any]) -> int:
        if ticket_id in self._store:
            self._store[ticket_id].update(data)
            return 1
        return 0


class MockDrawingRepo:
    def __init__(self, drawings: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for d in drawings or []:
            self._store[d["drawing_id"]] = dict(d)

    def find_by_id(self, drawing_id: str) -> dict[str, Any] | None:
        return self._store.get(drawing_id)

    def update(self, drawing_id: str, data: dict[str, Any]) -> int:
        if drawing_id in self._store:
            self._store[drawing_id].update(data)
            return 1
        return 0


class MockTransactionRepo:
    def __init__(self, balance: int = 0) -> None:
        self._balance = balance
        self._store: dict[str, dict[str, Any]] = {}

    def get_user_balance(self, user_id: str) -> int:
        return self._balance

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get("user_id") == user_id]

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"transaction_id": new_id, **data}


class MockUserRepo:
    def __init__(self, users: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for u in users or []:
            self._store[u["user_id"]] = dict(u)

    def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._store.get(user_id)

    def update(self, user_id: str, data: dict[str, Any]) -> int:
        if user_id in self._store:
            self._store[user_id].update(data)
            return 1
        return 0


# ── Factory ─────────────────────────────────────────────────────────

_OPEN_DRAW = {
    "drawing_id": "d1",
    "drawing_type": "daily",
    "name": "Daily Draw",
    "status": "open",
    "ticket_cost_points": 100,
    "total_tickets": 0,
    "ticket_sales_close": (datetime(2026, 3, 1, 18, 0, tzinfo=UTC)).isoformat(),
}


def _make_service(
    *,
    drawings: list[dict[str, Any]] | None = None,
    balance: int = 5000,
    users: list[dict[str, Any]] | None = None,
) -> TicketService:
    if users is None:
        users = [{"user_id": "u1", "point_balance": balance}]
    return TicketService(
        ticket_repo=MockTicketRepo(),
        drawing_repo=MockDrawingRepo(drawings or [_OPEN_DRAW]),
        transaction_repo=MockTransactionRepo(balance=balance),
        user_repo=MockUserRepo(users),
    )


# ── Purchase validation ────────────────────────────────────────────


class TestPurchaseValidation:
    def test_drawing_not_found(self):
        svc = _make_service(drawings=[])
        with pytest.raises(TicketError, match="Drawing not found"):
            svc.purchase_tickets(user_id="u1", drawing_id="nope")

    def test_drawing_not_open(self):
        closed = {**_OPEN_DRAW, "status": "draft"}
        svc = _make_service(drawings=[closed])
        with pytest.raises(TicketError, match="not open"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1")

    def test_sales_closed_past_deadline(self):
        draw = {
            **_OPEN_DRAW,
            "ticket_sales_close": datetime(2026, 3, 1, 17, 0, tzinfo=UTC).isoformat(),
        }
        svc = _make_service(drawings=[draw])
        now = datetime(2026, 3, 1, 17, 1, tzinfo=UTC)
        with pytest.raises(TicketError, match="sales have closed"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", now=now)

    def test_insufficient_balance(self):
        svc = _make_service(balance=50)  # need 100 for 1 ticket
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        with pytest.raises(TicketError, match="Insufficient points"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", now=now)

    def test_quantity_zero_rejected(self):
        svc = _make_service()
        with pytest.raises(TicketError, match="between 1 and 100"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=0)

    def test_quantity_negative_rejected(self):
        svc = _make_service()
        with pytest.raises(TicketError, match="between 1 and 100"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=-1)

    def test_quantity_over_100_rejected(self):
        svc = _make_service()
        with pytest.raises(TicketError, match="between 1 and 100"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=101)


# ── Successful purchase ────────────────────────────────────────────


class TestPurchaseSuccess:
    def test_single_ticket(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=1, now=now
        )
        assert result["quantity"] == 1
        assert result["total_cost"] == 100
        assert result["ticket_cost"] == 100
        assert result["new_balance"] == 400
        assert len(result["tickets"]) == 1

    def test_bulk_purchase_5_tickets(self):
        svc = _make_service(balance=1000)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=5, now=now
        )
        assert result["quantity"] == 5
        assert result["total_cost"] == 500
        assert result["new_balance"] == 500
        assert len(result["tickets"]) == 5

    def test_purchase_creates_transaction(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=1, now=now
        )
        assert result["purchase_id"]  # transaction ID
        txns = svc.transaction_repo._store
        assert len(txns) == 1
        txn = list(txns.values())[0]
        assert txn["transaction_type"] == "spend"
        assert txn["amount"] == -100

    def test_purchase_updates_drawing_total(self):
        svc = _make_service(balance=1000)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=3, now=now)
        drawing = svc.drawing_repo.find_by_id("d1")
        assert drawing["total_tickets"] == 3

    def test_purchase_deducts_user_balance(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=now)
        user = svc.user_repo.find_by_id("u1")
        assert user["point_balance"] == 300

    def test_purchase_exact_balance(self):
        svc = _make_service(balance=100)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=1, now=now
        )
        assert result["new_balance"] == 0

    def test_custom_ticket_cost(self):
        draw = {**_OPEN_DRAW, "ticket_cost_points": 250}
        svc = _make_service(drawings=[draw], balance=1000)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=2, now=now
        )
        assert result["total_cost"] == 500


# ── Query methods ──────────────────────────────────────────────────


class TestTicketQueries:
    def test_get_user_tickets_empty(self):
        svc = _make_service()
        result = svc.get_user_tickets("u1", "d1")
        assert result["count"] == 0
        assert result["tickets"] == []

    def test_get_user_tickets_after_purchase(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=3, now=now)
        result = svc.get_user_tickets("u1", "d1")
        assert result["count"] == 3
        assert len(result["tickets"]) == 3

    def test_get_drawing_tickets(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=now)
        tickets = svc.get_drawing_tickets("d1")
        assert len(tickets) == 2

    def test_tickets_belong_to_correct_drawing(self):
        draw2 = {**_OPEN_DRAW, "drawing_id": "d2"}
        svc = _make_service(drawings=[_OPEN_DRAW, draw2], balance=5000)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=now)
        svc.purchase_tickets(user_id="u1", drawing_id="d2", quantity=3, now=now)
        assert len(svc.get_drawing_tickets("d1")) == 2
        assert len(svc.get_drawing_tickets("d2")) == 3


# ── Edge cases ─────────────────────────────────────────────────────


class TestTicketEdgeCases:
    def test_sales_window_no_close_time(self):
        """When no ticket_sales_close is set, sales remain open."""
        draw = {**_OPEN_DRAW}
        del draw["ticket_sales_close"]
        svc = _make_service(drawings=[draw], balance=500)
        result = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1)
        assert result["quantity"] == 1

    def test_sales_window_at_exact_deadline(self):
        """Sales close AT the deadline (>=)."""
        close_time = datetime(2026, 3, 1, 17, 55, tzinfo=UTC)
        draw = {**_OPEN_DRAW, "ticket_sales_close": close_time.isoformat()}
        svc = _make_service(drawings=[draw], balance=500)
        with pytest.raises(TicketError, match="sales have closed"):
            svc.purchase_tickets(
                user_id="u1", drawing_id="d1", now=close_time
            )

    def test_sales_window_just_before_deadline(self):
        """Sales still open 1 second before deadline."""
        close_time = datetime(2026, 3, 1, 17, 55, tzinfo=UTC)
        draw = {**_OPEN_DRAW, "ticket_sales_close": close_time.isoformat()}
        svc = _make_service(drawings=[draw], balance=500)
        just_before = close_time - timedelta(seconds=1)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", now=just_before
        )
        assert result["quantity"] == 1

    def test_fallback_balance_sum(self):
        """If get_user_balance fails, falls back to summing transactions."""
        svc = _make_service(balance=0)
        # Override to raise
        svc.transaction_repo.get_user_balance = lambda uid: (_ for _ in ()).throw(
            RuntimeError("broken")
        )
        # Since fallback sum is 0, purchase should fail on balance
        with pytest.raises(TicketError, match="Insufficient"):
            svc.purchase_tickets(
                user_id="u1",
                drawing_id="d1",
                now=datetime(2026, 3, 1, 17, 0, tzinfo=UTC),
            )

    def test_ticket_data_structure(self):
        svc = _make_service(balance=500)
        now = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)
        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=1, now=now
        )
        ticket = result["tickets"][0]
        assert ticket["drawing_id"] == "d1"
        assert ticket["user_id"] == "u1"
        assert ticket["is_winner"] == 0
        assert ticket["ticket_id"]
        assert ticket["purchase_transaction_id"]
