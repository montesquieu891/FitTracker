"""TDD RED: Tests for entity-specific repositories — written BEFORE implementation."""

from __future__ import annotations

from datetime import datetime

import pytest

from tests.conftest import MockConnection, MockCursor, MockPool, set_mock_query_result


@pytest.fixture
def pool() -> MockPool:
    return MockPool()


@pytest.fixture
def conn(pool: MockPool) -> MockConnection:
    return pool._connection


@pytest.fixture
def cursor(conn: MockConnection) -> MockCursor:
    return conn._cursor


# ── User Repository ─────────────────────────────────────────────────

class TestUserRepository:
    """Test user-specific repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.user_repository import UserRepository
        return UserRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "users"
        assert repo.id_column == "user_id"

    def test_find_by_email(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["user_id", "email", "status"],
            rows=[("u1", "test@example.com", "active")],
        )
        repo = self._make_repo(pool)
        result = repo.find_by_email("test@example.com")
        assert result is not None
        assert result["email"] == "test@example.com"

    def test_find_by_email_not_found(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(cursor, columns=["user_id"], rows=[])
        repo = self._make_repo(pool)
        result = repo.find_by_email("missing@example.com")
        assert result is None

    def test_update_point_balance(self, pool: MockPool, cursor: MockCursor) -> None:
        cursor.rowcount = 1
        repo = self._make_repo(pool)
        affected = repo.update_point_balance("u1", new_balance=500)
        assert affected == 1

        sql, params = cursor._execute_log[-1]
        assert "UPDATE" in sql.upper()
        assert "point_balance" in sql.lower()

    def test_update_last_login(self, pool: MockPool, cursor: MockCursor) -> None:
        cursor.rowcount = 1
        repo = self._make_repo(pool)
        affected = repo.update_last_login("u1")
        assert affected == 1

        sql, _ = cursor._execute_log[-1]
        assert "last_login_at" in sql.lower()


# ── Profile Repository ──────────────────────────────────────────────

class TestProfileRepository:
    """Test profile-specific repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.profile_repository import ProfileRepository
        return ProfileRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "profiles"
        assert repo.id_column == "profile_id"

    def test_find_by_user_id(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["profile_id", "user_id", "display_name", "tier_code"],
            rows=[("p1", "u1", "TestUser", "M-18-29-BEG")],
        )
        repo = self._make_repo(pool)
        result = repo.find_by_user_id("u1")
        assert result is not None
        assert result["tier_code"] == "M-18-29-BEG"

    def test_find_by_tier_code(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["profile_id", "user_id", "tier_code"],
            rows=[
                ("p1", "u1", "F-30-39-INT"),
                ("p2", "u2", "F-30-39-INT"),
            ],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_tier_code("F-30-39-INT")
        assert len(results) == 2


# ── Activity Repository ─────────────────────────────────────────────

class TestActivityRepository:
    """Test activity-specific repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.activity_repository import ActivityRepository
        return ActivityRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "activities"
        assert repo.id_column == "activity_id"

    def test_find_by_user_id(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["activity_id", "user_id", "activity_type"],
            rows=[("a1", "u1", "steps"), ("a2", "u1", "workout")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user_id("u1")
        assert len(results) == 2

    def test_find_by_user_and_date_range(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["activity_id", "user_id", "start_time"],
            rows=[("a1", "u1", datetime(2026, 1, 15, 7, 0))],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user_and_date_range(
            user_id="u1",
            start_date=datetime(2026, 1, 15),
            end_date=datetime(2026, 1, 16),
        )
        assert len(results) == 1

        sql, params = cursor._execute_log[-1]
        assert "start_time" in sql.lower()


# ── Connection Repository ───────────────────────────────────────────

class TestConnectionRepository:
    """Test tracker connection repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.connection_repository import ConnectionRepository
        return ConnectionRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "tracker_connections"
        assert repo.id_column == "connection_id"

    def test_find_by_user_id(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["connection_id", "user_id", "provider"],
            rows=[("c1", "u1", "fitbit")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user_id("u1")
        assert len(results) == 1
        assert results[0]["provider"] == "fitbit"


# ── Transaction Repository ──────────────────────────────────────────

class TestTransactionRepository:
    """Test point transaction repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.transaction_repository import TransactionRepository
        return TransactionRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "point_transactions"
        assert repo.id_column == "transaction_id"

    def test_find_by_user_id(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["transaction_id", "user_id", "amount", "transaction_type"],
            rows=[("t1", "u1", 100, "earn"), ("t2", "u1", -50, "spend")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user_id("u1")
        assert len(results) == 2

    def test_get_balance(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["point_balance"],
            rows=[(750,)],
        )
        repo = self._make_repo(pool)
        balance = repo.get_user_balance("u1")
        assert balance == 750


# ── Drawing Repository ──────────────────────────────────────────────

class TestDrawingRepository:
    """Test drawing repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.drawing_repository import DrawingRepository
        return DrawingRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "drawings"
        assert repo.id_column == "drawing_id"

    def test_find_active(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["drawing_id", "name", "status"],
            rows=[("d1", "Daily Drawing", "open")],
        )
        repo = self._make_repo(pool)
        results = repo.find_active()
        assert len(results) == 1

        sql, _ = cursor._execute_log[-1]
        assert "open" in sql.lower() or "status" in sql.lower()

    def test_find_by_type(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["drawing_id", "drawing_type"],
            rows=[("d1", "weekly"), ("d2", "weekly")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_type("weekly")
        assert len(results) == 2


# ── Ticket Repository ───────────────────────────────────────────────

class TestTicketRepository:
    """Test ticket repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.ticket_repository import TicketRepository
        return TicketRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "tickets"
        assert repo.id_column == "ticket_id"

    def test_find_by_drawing(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["ticket_id", "drawing_id", "user_id"],
            rows=[("t1", "d1", "u1"), ("t2", "d1", "u2")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_drawing("d1")
        assert len(results) == 2

    def test_find_by_user(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["ticket_id", "drawing_id", "user_id"],
            rows=[("t1", "d1", "u1")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user("u1")
        assert len(results) == 1

    def test_count_by_drawing(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(cursor, columns=["cnt"], rows=[(15,)])
        repo = self._make_repo(pool)
        count = repo.count_by_drawing("d1")
        assert count == 15


# ── Prize Repository ────────────────────────────────────────────────

class TestPrizeRepository:
    """Test prize repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.prize_repository import PrizeRepository
        return PrizeRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "prizes"
        assert repo.id_column == "prize_id"

    def test_find_by_drawing(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["prize_id", "drawing_id", "name", "rank"],
            rows=[("p1", "d1", "Grand Prize", 1)],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_drawing("d1")
        assert len(results) == 1
        assert results[0]["name"] == "Grand Prize"


# ── Sponsor Repository ──────────────────────────────────────────────

class TestSponsorRepository:
    """Test sponsor repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.sponsor_repository import SponsorRepository
        return SponsorRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "sponsors"
        assert repo.id_column == "sponsor_id"

    def test_find_active(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["sponsor_id", "name", "status"],
            rows=[("s1", "Amazon", "active")],
        )
        repo = self._make_repo(pool)
        results = repo.find_active()
        assert len(results) == 1


# ── Fulfillment Repository ──────────────────────────────────────────

class TestFulfillmentRepository:
    """Test fulfillment repository methods."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        from fittrack.repositories.fulfillment_repository import FulfillmentRepository
        return FulfillmentRepository(pool=pool)

    def test_table_name(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        assert repo.table_name == "prize_fulfillments"
        assert repo.id_column == "fulfillment_id"

    def test_find_by_user(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["fulfillment_id", "user_id", "status"],
            rows=[("f1", "u1", "pending")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_user("u1")
        assert len(results) == 1

    def test_find_pending(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["fulfillment_id", "status"],
            rows=[("f1", "pending"), ("f2", "pending")],
        )
        repo = self._make_repo(pool)
        results = repo.find_pending()
        assert len(results) == 2
