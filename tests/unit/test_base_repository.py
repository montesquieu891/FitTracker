"""TDD RED: Tests for the base repository — written BEFORE implementation."""

from __future__ import annotations

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


class TestBaseRepository:
    """Test the BaseRepository generic CRUD operations."""

    def _make_repo(self, pool: MockPool):  # type: ignore[no-untyped-def]
        """Create a BaseRepository instance with mock pool."""
        from fittrack.repositories.base import BaseRepository

        return BaseRepository(
            pool=pool,
            table_name="users",
            id_column="user_id",
        )

    def test_find_by_id_returns_dict(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["user_id", "email", "status"],
            rows=[("abc123", "test@example.com", "active")],
        )
        repo = self._make_repo(pool)
        result = repo.find_by_id("abc123")

        assert result is not None
        assert result["user_id"] == "abc123"
        assert result["email"] == "test@example.com"

    def test_find_by_id_returns_none_when_not_found(
        self, pool: MockPool, cursor: MockCursor,
    ) -> None:
        set_mock_query_result(cursor, columns=["user_id"], rows=[])
        repo = self._make_repo(pool)
        result = repo.find_by_id("nonexistent")
        assert result is None

    def test_find_all_returns_list(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["user_id", "email"],
            rows=[
                ("u1", "a@example.com"),
                ("u2", "b@example.com"),
            ],
        )
        repo = self._make_repo(pool)
        results = repo.find_all(limit=20, offset=0)

        assert len(results) == 2
        assert results[0]["user_id"] == "u1"
        assert results[1]["email"] == "b@example.com"

    def test_find_all_with_filters(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["user_id", "email"],
            rows=[("u1", "a@example.com")],
        )
        repo = self._make_repo(pool)
        repo.find_all(limit=20, offset=0, filters={"status": "active"})

        # Verify a WHERE clause was constructed
        sql, params = cursor._execute_log[-1]
        assert "WHERE" in sql.upper()
        assert params is not None
        assert "active" in str(params.values())

    def test_count_returns_integer(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(cursor, columns=["cnt"], rows=[(42,)])
        repo = self._make_repo(pool)
        result = repo.count()
        assert result == 42

    def test_count_with_filters(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(cursor, columns=["cnt"], rows=[(5,)])
        repo = self._make_repo(pool)
        result = repo.count(filters={"status": "active"})

        sql, params = cursor._execute_log[-1]
        assert "WHERE" in sql.upper()
        assert result == 5

    def test_create_returns_id(self, pool: MockPool, cursor: MockCursor) -> None:
        cursor.rowcount = 1
        repo = self._make_repo(pool)
        result_id = repo.create(
            data={"email": "new@example.com", "status": "pending"},
            new_id="new_uuid_123",
        )
        assert result_id == "new_uuid_123"

        # Verify INSERT was executed
        sql, _ = cursor._execute_log[-1]
        assert "INSERT" in sql.upper()

    def test_update_returns_rows_affected(self, pool: MockPool, cursor: MockCursor) -> None:
        cursor.rowcount = 1
        repo = self._make_repo(pool)
        affected = repo.update("abc123", data={"status": "active"})
        assert affected == 1

        sql, params = cursor._execute_log[-1]
        assert "UPDATE" in sql.upper()
        assert "abc123" in str(params.values())

    def test_update_no_data_raises(self, pool: MockPool) -> None:
        repo = self._make_repo(pool)
        with pytest.raises(ValueError, match="No data"):
            repo.update("abc123", data={})

    def test_delete_returns_rows_affected(self, pool: MockPool, cursor: MockCursor) -> None:
        cursor.rowcount = 1
        repo = self._make_repo(pool)
        affected = repo.delete("abc123")
        assert affected == 1

        sql, params = cursor._execute_log[-1]
        assert "DELETE" in sql.upper()

    def test_find_by_field_returns_matching(self, pool: MockPool, cursor: MockCursor) -> None:
        set_mock_query_result(
            cursor,
            columns=["user_id", "email"],
            rows=[("u1", "test@example.com")],
        )
        repo = self._make_repo(pool)
        results = repo.find_by_field("email", "test@example.com")
        assert len(results) == 1
        assert results[0]["email"] == "test@example.com"
