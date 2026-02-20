"""Checkpoint H2 — Integration tests requiring Oracle + Redis.

These tests connect to the real local Oracle DB and verify:
  - Health ready/live semantics with real DB
  - Migrations are idempotent
  - Seed data + sanity API reads
  - Basic auth flow against real DB

Tests are skipped automatically if Oracle is not reachable.

Run with:  make test-integration  (or pytest -m integration)
"""

from __future__ import annotations

import os
import sys
from typing import Any

import pytest

# Ensure src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# ── Skip if Oracle is unreachable ───────────────────────────────────

_ORACLE_DSN = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
_ORACLE_USER = os.getenv("ORACLE_USER", "fittrack")
_ORACLE_PASSWORD = os.getenv("ORACLE_PASSWORD", "FitTrack_Dev_2026!")


def _oracle_available() -> bool:
    """Return True if we can connect to Oracle."""
    try:
        import oracledb

        conn = oracledb.connect(
            user=_ORACLE_USER, password=_ORACLE_PASSWORD, dsn=_ORACLE_DSN
        )
        conn.close()
        return True
    except Exception:
        return False


_SKIP_REASON = "Oracle DB not reachable (set ORACLE_DSN or start Docker)"
_oracle_ok = _oracle_available()

pytestmark = pytest.mark.integration


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def oracle_conn():
    """Provide a live Oracle connection for the test module."""
    if not _oracle_ok:
        pytest.skip(_SKIP_REASON)
    import oracledb

    conn = oracledb.connect(
        user=_ORACLE_USER, password=_ORACLE_PASSWORD, dsn=_ORACLE_DSN
    )
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def oracle_pool():
    """Provide a live Oracle pool for the test module."""
    if not _oracle_ok:
        pytest.skip(_SKIP_REASON)
    import oracledb

    pool = oracledb.create_pool(
        user=_ORACLE_USER,
        password=_ORACLE_PASSWORD,
        dsn=_ORACLE_DSN,
        min=1,
        max=4,
        increment=1,
    )
    yield pool
    pool.close(force=True)


# ── H2: Health ready/live semantics ─────────────────────────────────


@pytest.mark.skipif(not _oracle_ok, reason=_SKIP_REASON)
class TestH2HealthWithRealDB:
    """Health endpoints against real DB."""

    def test_health_live(self) -> None:
        """GET /health/live returns 200 regardless of DB."""
        from unittest.mock import patch

        from fastapi.testclient import TestClient

        from fittrack.core.config import Settings
        from fittrack.main import create_app

        app = create_app(settings=Settings(app_env="testing"))
        client = TestClient(app)
        resp = client.get("/health/live")
        assert resp.status_code == 200
        assert resp.json()["status"] == "alive"

    def test_health_ready_structure(self) -> None:
        """GET /health/ready response has expected keys."""
        from fastapi.testclient import TestClient

        from fittrack.core.config import Settings
        from fittrack.main import create_app

        app = create_app(settings=Settings(app_env="testing"))
        client = TestClient(app)
        resp = client.get("/health/ready")
        data = resp.json()
        assert "status" in data
        assert "checks" in data
        assert data["status"] in ("ready", "not_ready")


# ── H2: Migrations idempotent ──────────────────────────────────────


@pytest.mark.skipif(not _oracle_ok, reason=_SKIP_REASON)
class TestH2MigrationsIdempotent:
    """Running migrations twice doesn't fail."""

    def test_run_migrations_twice(self, oracle_conn) -> None:
        from scripts.migrations import run_migrations

        result1 = run_migrations(oracle_conn)
        result2 = run_migrations(oracle_conn)
        # Both should succeed (second run = all tables exist already)
        assert isinstance(result1, list)
        assert isinstance(result2, list)

    def test_tables_exist(self, oracle_conn) -> None:
        """After migration, expected tables are present."""
        with oracle_conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM user_tables ORDER BY table_name"
            )
            tables = {row[0].upper() for row in cur.fetchall()}

        expected = {"USERS", "PROFILES", "ACTIVITIES", "DRAWINGS", "TICKETS"}
        assert expected.issubset(tables), f"Missing: {expected - tables}"


# ── H2: Seed + sanity API reads ────────────────────────────────────


@pytest.mark.skipif(not _oracle_ok, reason=_SKIP_REASON)
class TestH2SeedSanity:
    """After seeding, basic API reads return data."""

    def test_users_exist(self, oracle_conn) -> None:
        """At least one user exists after seed."""
        with oracle_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
        assert count > 0, "No users found — was DB seeded?"

    def test_sponsors_exist(self, oracle_conn) -> None:
        with oracle_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sponsors")
            count = cur.fetchone()[0]
        assert count > 0

    def test_drawings_exist(self, oracle_conn) -> None:
        with oracle_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM drawings")
            count = cur.fetchone()[0]
        assert count > 0

    def test_activities_exist(self, oracle_conn) -> None:
        with oracle_conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM activities")
            count = cur.fetchone()[0]
        assert count > 0


# ── H2: Auth basic flow with real DB ───────────────────────────────


@pytest.mark.skipif(not _oracle_ok, reason=_SKIP_REASON)
class TestH2AuthReal:
    """Register → login → me against real Oracle."""

    _EMAIL = "h2_integ_test@fittrack.dev"
    _PASSWORD = "H2IntegP@ss2026!"

    def _cleanup(self, oracle_conn) -> None:
        """Remove test user if exists."""
        with oracle_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM sessions WHERE user_id IN "
                "(SELECT user_id FROM users WHERE email = :email)",
                {"email": self._EMAIL},
            )
            cur.execute(
                "DELETE FROM users WHERE email = :email",
                {"email": self._EMAIL},
            )
            oracle_conn.commit()

    def test_register_login_me(self, oracle_pool, oracle_conn) -> None:
        """Full register → login → /me round-trip."""
        from unittest.mock import patch

        import fittrack.core.database as db_mod
        from fittrack.repositories.session_repository import SessionRepository
        from fittrack.repositories.user_repository import UserRepository
        from fittrack.services.auth import AuthService

        # Cleanup any prior test user
        self._cleanup(oracle_conn)

        # Wire up real repos
        user_repo = UserRepository(pool=oracle_pool)
        session_repo = SessionRepository(pool=oracle_pool)
        svc = AuthService(user_repo=user_repo, session_repo=session_repo)

        # Register
        reg = svc.register(
            email=self._EMAIL,
            password=self._PASSWORD,
            date_of_birth="1995-06-15",
            state="CA",
        )
        assert "user_id" in reg
        assert "access_token" in reg

        # Login
        login_result = svc.login(email=self._EMAIL, password=self._PASSWORD)
        assert "access_token" in login_result
        assert login_result["role"] == "user"

        # Fetch user by ID
        user = user_repo.find_by_id(reg["user_id"])
        assert user is not None
        assert user["email"] == self._EMAIL

        # Cleanup
        self._cleanup(oracle_conn)
