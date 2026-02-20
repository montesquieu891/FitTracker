"""Tests for ticket purchase concurrency and race conditions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from fittrack.services.tickets import TicketError, TicketService

# ── Mock repositories (shared) ─────────────────────────────────────


class MockTicketRepo:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"ticket_id": new_id, **data}

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get("drawing_id") == drawing_id]

    def update(self, tid: str, data: dict[str, Any]) -> int:
        if tid in self._store:
            self._store[tid].update(data)
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
        if data.get("transaction_type") == "spend":
            self._balance += data.get("amount", 0)  # amount is negative


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


_OPEN_DRAW = {
    "drawing_id": "d1",
    "drawing_type": "daily",
    "name": "Test",
    "status": "open",
    "ticket_cost_points": 100,
    "total_tickets": 0,
    "ticket_sales_close": datetime(2026, 3, 1, 18, 0, tzinfo=UTC).isoformat(),
}

NOW = datetime(2026, 3, 1, 17, 0, tzinfo=UTC)


# ── Sequential purchase tests (simulated concurrency) ──────────────


class TestSequentialPurchases:
    """Simulate race conditions with sequential operations on shared state."""

    def test_two_users_buy_same_drawing(self):
        """Two users purchasing tickets for the same drawing."""
        users = [
            {"user_id": "u1", "point_balance": 500},
            {"user_id": "u2", "point_balance": 500},
        ]
        txn_repo = MockTransactionRepo(balance=500)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        r1 = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=NOW)
        assert r1["quantity"] == 2

        # Reset balance for second user
        txn_repo._balance = 500
        r2 = svc.purchase_tickets(user_id="u2", drawing_id="d1", quantity=3, now=NOW)
        assert r2["quantity"] == 3

        # Drawing should have 5 total tickets
        drawing = svc.drawing_repo.find_by_id("d1")
        assert drawing["total_tickets"] == 5

    def test_user_buys_until_balance_exhausted(self):
        """User purchases until they can't afford more."""
        users = [{"user_id": "u1", "point_balance": 300}]
        txn_repo = MockTransactionRepo(balance=300)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        r1 = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=NOW)
        assert r1["new_balance"] == 100

        # Balance decreased on transaction repo
        txn_repo._balance = 100

        # Can still buy 1 more
        r2 = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1, now=NOW)
        assert r2["new_balance"] == 0

        # Now balance is 0
        txn_repo._balance = 0
        with pytest.raises(TicketError, match="Insufficient"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1, now=NOW)

    def test_multiple_drawings_separate_balances(self):
        """Buying tickets for different drawings deducts independently."""
        draw2 = {**_OPEN_DRAW, "drawing_id": "d2"}
        users = [{"user_id": "u1", "point_balance": 500}]
        txn_repo = MockTransactionRepo(balance=500)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW, draw2]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        r1 = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=NOW)
        assert r1["total_cost"] == 200

        txn_repo._balance = 300
        r2 = svc.purchase_tickets(user_id="u1", drawing_id="d2", quantity=3, now=NOW)
        assert r2["total_cost"] == 300

    def test_transaction_created_per_purchase(self):
        """Each purchase creates its own spend transaction."""
        users = [{"user_id": "u1", "point_balance": 1000}]
        txn_repo = MockTransactionRepo(balance=1000)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=NOW)
        txn_repo._balance = 800
        svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1, now=NOW)

        assert len(txn_repo._store) == 2
        amounts = [t["amount"] for t in txn_repo._store.values()]
        assert sorted(amounts) == [-200, -100]


# ── Edge case scenarios ─────────────────────────────────────────────


class TestConcurrencyEdgeCases:
    def test_exact_balance_race(self):
        """Two purchases that together exceed balance but individually pass."""
        users = [{"user_id": "u1", "point_balance": 200}]
        txn_repo = MockTransactionRepo(balance=200)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        # First purchase succeeds
        r1 = svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=2, now=NOW)
        assert r1["new_balance"] == 0

        # Simulate balance now 0
        txn_repo._balance = 0

        # Second purchase should fail
        with pytest.raises(TicketError, match="Insufficient"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1, now=NOW)

    def test_bulk_purchase_all_or_nothing(self):
        """Bulk purchase fails entirely if insufficient for total."""
        users = [{"user_id": "u1", "point_balance": 250}]
        txn_repo = MockTransactionRepo(balance=250)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        # Can afford 2 but not 3
        with pytest.raises(TicketError, match="Insufficient"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=3, now=NOW)

        # No tickets should have been created
        assert len(svc.ticket_repo._store) == 0

    def test_status_change_mid_purchase(self):
        """If drawing status changes to not-open, purchase fails."""
        closed_draw = {**_OPEN_DRAW, "status": "closed"}
        users = [{"user_id": "u1", "point_balance": 500}]
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([closed_draw]),
            transaction_repo=MockTransactionRepo(balance=500),
            user_repo=MockUserRepo(users),
        )

        with pytest.raises(TicketError, match="not open"):
            svc.purchase_tickets(user_id="u1", drawing_id="d1", quantity=1, now=NOW)

    def test_max_quantity_100(self):
        """Can purchase exactly 100 tickets at once."""
        users = [{"user_id": "u1", "point_balance": 100000}]
        txn_repo = MockTransactionRepo(balance=100000)
        svc = TicketService(
            ticket_repo=MockTicketRepo(),
            drawing_repo=MockDrawingRepo([_OPEN_DRAW]),
            transaction_repo=txn_repo,
            user_repo=MockUserRepo(users),
        )

        result = svc.purchase_tickets(
            user_id="u1", drawing_id="d1", quantity=100, now=NOW
        )
        assert result["quantity"] == 100
        assert len(result["tickets"]) == 100
