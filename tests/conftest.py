"""Shared pytest fixtures and test configuration."""

from __future__ import annotations

import os
import sys
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure src is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


class MockCursor:
    """Mock Oracle cursor supporting context manager and common operations."""

    def __init__(self) -> None:
        self.description: list[tuple[str, ...]] | None = None
        self._rows: list[tuple[Any, ...]] = []
        self._execute_log: list[tuple[str, dict[str, Any] | None]] = []
        self.rowcount: int = 0
        self._var_values: dict[str, Any] = {}

    def execute(self, sql: str, params: dict[str, Any] | None = None) -> None:
        self._execute_log.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows

    def fetchone(self) -> tuple[Any, ...] | None:
        return self._rows[0] if self._rows else None

    def var(self, type_: Any) -> MagicMock:
        mock_var = MagicMock()
        mock_var.getvalue.return_value = None
        return mock_var

    def __enter__(self) -> MockCursor:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class MockConnection:
    """Mock Oracle connection supporting context manager."""

    def __init__(self) -> None:
        self._cursor = MockCursor()
        self._committed = False
        self._closed = False

    def cursor(self) -> MockCursor:
        return self._cursor

    def commit(self) -> None:
        self._committed = True

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> MockConnection:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class MockPool:
    """Mock Oracle connection pool."""

    def __init__(self) -> None:
        self._connection = MockConnection()

    def acquire(self) -> MockConnection:
        return self._connection

    def close(self, force: bool = False) -> None:
        pass


@pytest.fixture
def mock_pool() -> MockPool:
    """Provide a mock Oracle connection pool."""
    return MockPool()


@pytest.fixture
def mock_connection(mock_pool: MockPool) -> MockConnection:
    """Provide a mock Oracle connection."""
    return mock_pool._connection


@pytest.fixture
def mock_cursor(mock_connection: MockConnection) -> MockCursor:
    """Provide a mock Oracle cursor."""
    return mock_connection._cursor


@pytest.fixture
def patch_db_pool(mock_pool: MockPool) -> Generator[MockPool, None, None]:
    """Patch the database module to use mock pool."""
    with (
        patch("fittrack.core.database._pool", mock_pool),
        patch("fittrack.core.database.get_pool", return_value=mock_pool),
        patch("fittrack.core.database.get_connection", return_value=mock_pool.acquire()),
    ):
        yield mock_pool


@pytest.fixture
def app(patch_db_pool: MockPool):  # type: ignore[no-untyped-def]
    """Create a FastAPI test app with mocked database."""
    from fittrack.core.config import Settings
    from fittrack.main import create_app

    settings = Settings(app_env="testing")
    application = create_app(settings=settings)
    return application


@pytest.fixture
def client(app):  # type: ignore[no-untyped-def]
    """Create a test client."""
    return TestClient(app)


# ── Helper for setting up mock query results ─────────────────────────

def set_mock_query_result(
    cursor: MockCursor,
    columns: list[str],
    rows: list[tuple[Any, ...]],
) -> None:
    """Configure mock cursor to return specific query results."""
    cursor.description = [(col.upper(),) for col in columns]
    cursor._rows = rows
    cursor.rowcount = len(rows)


# ── Auth helpers for protected route tests ───────────────────────────


@pytest.fixture
def admin_headers() -> dict[str, str]:
    """Return Authorization headers with a valid admin JWT."""
    from fittrack.core.security import create_access_token

    token = create_access_token(subject="test-admin", role="admin")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def user_headers() -> dict[str, str]:
    """Return Authorization headers with a valid user JWT."""
    from fittrack.core.security import create_access_token

    token = create_access_token(subject="test-user", role="user")
    return {"Authorization": f"Bearer {token}"}
