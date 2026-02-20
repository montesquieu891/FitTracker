"""Tests for drawing executor — CSPRNG winner selection with audit trail."""

from __future__ import annotations

from typing import Any

import pytest

from fittrack.services.drawing_executor import DrawingExecutor, ExecutionError

# ── Mock repositories ───────────────────────────────────────────────


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


class MockTicketRepo:
    def __init__(self, tickets: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for t in tickets or []:
            self._store[t["ticket_id"]] = dict(t)

    def find_by_drawing(self, drawing_id: str) -> list[dict[str, Any]]:
        return [t for t in self._store.values() if t.get("drawing_id") == drawing_id]

    def update(self, ticket_id: str, data: dict[str, Any]) -> int:
        if ticket_id in self._store:
            self._store[ticket_id].update(data)
            return 1
        return 0


class MockPrizeRepo:
    def __init__(self, prizes: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for p in prizes or []:
            self._store[p["prize_id"]] = dict(p)

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [p for p in self._store.values() if p.get(field) == value]


class MockFulfillmentRepo:
    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"fulfillment_id": new_id, **data}

    def find_by_id(self, fid: str) -> dict[str, Any] | None:
        return self._store.get(fid)


# ── Factory ─────────────────────────────────────────────────────────


def _make_tickets(drawing_id: str, user_ids: list[str], per_user: int = 1) -> list[dict[str, Any]]:
    """Create tickets for given users."""
    tickets = []
    idx = 0
    for uid in user_ids:
        for _ in range(per_user):
            idx += 1
            tickets.append(
                {
                    "ticket_id": f"t{idx:04d}",
                    "drawing_id": drawing_id,
                    "user_id": uid,
                    "is_winner": 0,
                }
            )
    return tickets


def _make_prizes(drawing_id: str, count: int = 1, quantity: int = 1) -> list[dict[str, Any]]:
    """Create prizes for a drawing."""
    return [
        {
            "prize_id": f"p{i + 1}",
            "drawing_id": drawing_id,
            "name": f"Prize {i + 1}",
            "rank": i + 1,
            "quantity": quantity,
        }
        for i in range(count)
    ]


_CLOSED_DRAW = {
    "drawing_id": "d1",
    "drawing_type": "daily",
    "name": "Test Draw",
    "status": "closed",
}


def _make_executor(
    drawing: dict[str, Any] | None = None,
    tickets: list[dict[str, Any]] | None = None,
    prizes: list[dict[str, Any]] | None = None,
) -> DrawingExecutor:
    return DrawingExecutor(
        drawing_repo=MockDrawingRepo([drawing] if drawing else []),
        ticket_repo=MockTicketRepo(tickets or []),
        prize_repo=MockPrizeRepo(prizes or []),
        fulfillment_repo=MockFulfillmentRepo(),
    )


# ── Validation tests ───────────────────────────────────────────────


class TestExecutionValidation:
    def test_drawing_not_found(self):
        executor = _make_executor()
        with pytest.raises(ExecutionError, match="not found"):
            executor.execute("nonexistent")

    def test_already_completed(self):
        draw = {**_CLOSED_DRAW, "status": "completed"}
        executor = _make_executor(drawing=draw)
        with pytest.raises(ExecutionError, match="already executed"):
            executor.execute("d1")

    def test_not_closed_status(self):
        draw = {**_CLOSED_DRAW, "status": "open"}
        executor = _make_executor(drawing=draw)
        with pytest.raises(ExecutionError, match="must be in 'closed'"):
            executor.execute("d1")

    def test_no_tickets(self):
        executor = _make_executor(
            drawing=_CLOSED_DRAW,
            prizes=_make_prizes("d1"),
        )
        with pytest.raises(ExecutionError, match="No tickets"):
            executor.execute("d1")

    def test_no_prizes(self):
        tickets = _make_tickets("d1", ["u1"])
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets)
        with pytest.raises(ExecutionError, match="No prizes"):
            executor.execute("d1")


# ── Snapshot tests ──────────────────────────────────────────────────


class TestSnapshot:
    def test_sequential_numbers(self):
        tickets = _make_tickets("d1", ["u1", "u2", "u3"])
        executor = _make_executor()
        snapshot = executor._create_snapshot(tickets)
        numbers = [e["ticket_number"] for e in snapshot]
        assert numbers == [1, 2, 3]

    def test_deterministic_sorting(self):
        """Snapshot order is deterministic regardless of input order."""
        tickets = [
            {"ticket_id": "t003", "drawing_id": "d1", "user_id": "u3"},
            {"ticket_id": "t001", "drawing_id": "d1", "user_id": "u1"},
            {"ticket_id": "t002", "drawing_id": "d1", "user_id": "u2"},
        ]
        executor = _make_executor()
        snapshot = executor._create_snapshot(tickets)
        ids = [e["ticket_id"] for e in snapshot]
        assert ids == ["t001", "t002", "t003"]

    def test_snapshot_preserves_user_id(self):
        tickets = _make_tickets("d1", ["alice", "bob"])
        executor = _make_executor()
        snapshot = executor._create_snapshot(tickets)
        user_ids = {e["user_id"] for e in snapshot}
        assert user_ids == {"alice", "bob"}


# ── Winner selection tests ──────────────────────────────────────────


class TestWinnerSelection:
    def test_single_winner(self):
        tickets = _make_tickets("d1", ["u1", "u2", "u3"], per_user=2)
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["winners"]) == 1
        assert result["winners"][0]["user_id"] in {"u1", "u2", "u3"}

    def test_multiple_prizes(self):
        tickets = _make_tickets("d1", [f"u{i}" for i in range(10)], per_user=2)
        prizes = _make_prizes("d1", count=3)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["winners"]) == 3

    def test_one_win_per_user(self):
        """Each user can only win once per drawing."""
        # 3 users with many tickets each
        tickets = _make_tickets("d1", ["u1", "u2", "u3"], per_user=10)
        prizes = _make_prizes("d1", count=3)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        winner_ids = [w["user_id"] for w in result["winners"]]
        # All three different users should win
        assert len(set(winner_ids)) == 3

    def test_more_prizes_than_users(self):
        """If more prizes than unique users, some prizes go unawarded."""
        tickets = _make_tickets("d1", ["u1", "u2"], per_user=5)
        prizes = _make_prizes("d1", count=5)  # 5 prizes but only 2 users
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        # At most 2 winners (one per user)
        assert len(result["winners"]) <= 2

    def test_single_user_single_prize(self):
        """One user with many tickets wins the single prize."""
        tickets = _make_tickets("d1", ["u1"], per_user=10)
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["winners"]) == 1
        assert result["winners"][0]["user_id"] == "u1"


# ── Audit trail tests ──────────────────────────────────────────────


class TestAuditTrail:
    def test_result_has_seed_hash(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert result["random_seed_hash"]
        assert len(result["random_seed_hash"]) == 64  # SHA-256 hex

    def test_result_has_algorithm(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert result["algorithm"] == "secrets.randbelow"

    def test_result_has_total_tickets(self):
        tickets = _make_tickets("d1", ["u1", "u2", "u3"], per_user=2)
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert result["total_tickets"] == 6

    def test_result_has_executed_at(self):
        tickets = _make_tickets("d1", ["u1"])
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert result["executed_at"]

    def test_drawing_marked_completed(self):
        tickets = _make_tickets("d1", ["u1"])
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        executor.execute("d1")
        drawing = executor.drawing_repo.find_by_id("d1")
        assert drawing["status"] == "completed"
        assert drawing["completed_at"]
        assert drawing["random_seed"]  # hash stored on drawing

    def test_seed_hash_is_sha256(self):
        tickets = _make_tickets("d1", ["u1"])
        prizes = _make_prizes("d1")
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        # Verify it's valid hex
        int(result["random_seed_hash"], 16)


# ── Fulfillment creation ───────────────────────────────────────────


class TestFulfillmentCreation:
    def test_fulfillments_created_for_winners(self):
        tickets = _make_tickets("d1", ["u1", "u2", "u3"], per_user=3)
        prizes = _make_prizes("d1", count=2)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["fulfillments"]) == 2
        for f in result["fulfillments"]:
            assert f["status"] == "pending"
            assert f["drawing_id"] == "d1"
            assert f["fulfillment_id"]

    def test_fulfillment_records_in_repo(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        executor.execute("d1")
        stored = executor.fulfillment_repo._store
        assert len(stored) == 1

    def test_fulfillment_links_user_and_prize(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        f = result["fulfillments"][0]
        assert f["user_id"] in {"u1", "u2"}
        assert f["prize_id"] == "p1"


# ── Winner ticket marking ──────────────────────────────────────────


class TestTicketMarking:
    def test_winning_tickets_marked(self):
        tickets = _make_tickets("d1", ["u1", "u2"], per_user=3)
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        executor.execute("d1")
        # Check ticket store for winner marks
        winning = [t for t in executor.ticket_repo._store.values() if t.get("is_winner") == 1]
        assert len(winning) == 1

    def test_winner_has_prize_id(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        executor.execute("d1")
        winning = [t for t in executor.ticket_repo._store.values() if t.get("is_winner") == 1]
        assert winning[0]["prize_id"] == "p1"

    def test_winner_has_ticket_number(self):
        tickets = _make_tickets("d1", ["u1", "u2"])
        prizes = _make_prizes("d1", count=1)
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        executor.execute("d1")
        winning = [t for t in executor.ticket_repo._store.values() if t.get("is_winner") == 1]
        assert winning[0].get("ticket_number") is not None
        assert winning[0]["ticket_number"] >= 1


# ── Prize with quantity tests ──────────────────────────────────────


class TestPrizeQuantity:
    def test_single_prize_quantity_3(self):
        """A single prize with quantity=3 gives 3 winners."""
        users = [f"u{i}" for i in range(10)]
        tickets = _make_tickets("d1", users, per_user=2)
        prizes = [{"prize_id": "p1", "drawing_id": "d1", "name": "Prize", "rank": 1, "quantity": 3}]
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["winners"]) == 3
        # All unique users
        assert len({w["user_id"] for w in result["winners"]}) == 3

    def test_quantity_exceeds_users(self):
        """If prize quantity exceeds unique users, award what we can."""
        tickets = _make_tickets("d1", ["u1", "u2"], per_user=5)
        prizes = [{"prize_id": "p1", "drawing_id": "d1", "name": "Prize", "rank": 1, "quantity": 5}]
        executor = _make_executor(drawing=_CLOSED_DRAW, tickets=tickets, prizes=prizes)
        result = executor.execute("d1")
        assert len(result["winners"]) <= 2
