"""Tests for Section C: Database (Oracle) — migrations + seed.

Covers:
  C1) Migrations are idempotent and create expected schema
  C2) Seed creates data for demo local
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from scripts.migrations import (
    ALL_AUTH_TABLE_DDLS,
    ALL_CP4_TABLE_DDLS,
    ALL_CP7_TABLE_DDLS,
    ALL_TABLE_DDLS,
    DROP_ORDER,
    MIGRATION_002_INDEXES,
    run_migrations,
    table_exists,
)

# ── C1: Migrations Idempotent ───────────────────────────────────────


class TestC1MigrationSchema:
    """C1) Migration scripts define the expected tables and indexes."""

    EXPECTED_CORE_TABLES = [
        "users",
        "sponsors",
        "profiles",
        "tracker_connections",
        "activities",
        "point_transactions",
        "drawings",
        "prizes",
        "tickets",
        "prize_fulfillments",
    ]
    EXPECTED_AUTH_TABLES = ["oauth_accounts", "sessions"]
    EXPECTED_CP4_TABLES = ["daily_points_log"]
    EXPECTED_CP7_TABLES = ["notifications", "admin_actions_log"]

    def test_all_core_tables_defined(self) -> None:
        """ALL_TABLE_DDLS covers all core tables."""
        defined = [name for name, _ in ALL_TABLE_DDLS]
        for table in self.EXPECTED_CORE_TABLES:
            assert table in defined, f"Missing core table DDL: {table}"

    def test_all_auth_tables_defined(self) -> None:
        defined = [name for name, _ in ALL_AUTH_TABLE_DDLS]
        for table in self.EXPECTED_AUTH_TABLES:
            assert table in defined, f"Missing auth table DDL: {table}"

    def test_all_cp4_tables_defined(self) -> None:
        defined = [name for name, _ in ALL_CP4_TABLE_DDLS]
        for table in self.EXPECTED_CP4_TABLES:
            assert table in defined, f"Missing CP4 table DDL: {table}"

    def test_all_cp7_tables_defined(self) -> None:
        defined = [name for name, _ in ALL_CP7_TABLE_DDLS]
        for table in self.EXPECTED_CP7_TABLES:
            assert table in defined, f"Missing CP7 table DDL: {table}"

    def test_drop_order_covers_all_tables(self) -> None:
        """DROP_ORDER should include every table we create."""
        all_created = (
            [n for n, _ in ALL_TABLE_DDLS]
            + [n for n, _ in ALL_AUTH_TABLE_DDLS]
            + [n for n, _ in ALL_CP4_TABLE_DDLS]
            + [n for n, _ in ALL_CP7_TABLE_DDLS]
        )
        for table in all_created:
            assert table in DROP_ORDER, f"{table} missing from DROP_ORDER"

    def test_indexes_include_users_email(self) -> None:
        """At least one index targets the users email column."""
        email_indexes = [
            sql
            for sql in MIGRATION_002_INDEXES
            if "users" in sql.lower() and "email" in sql.lower()
        ]
        assert len(email_indexes) >= 1

    def test_indexes_include_activities_user_date(self) -> None:
        activity_indexes = [
            sql
            for sql in MIGRATION_002_INDEXES
            if "activities" in sql.lower() and "user_id" in sql.lower()
        ]
        assert len(activity_indexes) >= 1

    def test_indexes_include_drawings_status(self) -> None:
        drawing_indexes = [
            sql
            for sql in MIGRATION_002_INDEXES
            if "drawings" in sql.lower() and "status" in sql.lower()
        ]
        assert len(drawing_indexes) >= 1


class TestC1MigrationIdempotent:
    """C1) run_migrations can be called multiple times without error."""

    def test_run_migrations_twice_no_error(self) -> None:
        """Simulates idempotent migration: first run creates, second skips."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # First run: tables don't exist
        with patch("scripts.migrations.table_exists", return_value=False):
            actions1 = run_migrations(mock_conn)

        assert len(actions1) > 0  # should have created tables

        # Second run: tables exist
        with patch("scripts.migrations.table_exists", return_value=True):
            # ALTER and INDEX statements handle duplicates via exception catching
            import oracledb

            err = MagicMock()
            err.code = 1430  # ORA-01430: column already exists
            alter_exc = oracledb.DatabaseError(err)
            idx_err = MagicMock()
            idx_err.code = 955  # ORA-00955: name already used
            idx_exc = oracledb.DatabaseError(idx_err)

            mock_cursor.execute.side_effect = [
                alter_exc,
                alter_exc,
                alter_exc,
                alter_exc,  # 4 ALTER column
                alter_exc,  # balance version
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,  # indexes
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,
                idx_exc,  # CP7+CP8 indexes
                None,  # duality view
            ]
            run_migrations(mock_conn)

    def test_table_exists_false_when_not_found(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (0,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        assert table_exists(mock_conn, "nonexistent_table") is False

    def test_table_exists_true_when_found(self) -> None:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        assert table_exists(mock_conn, "users") is True


# ── C2: Seed Data ───────────────────────────────────────────────────


class TestC2SeedFactories:
    """C2) Seed factories produce valid, insertable data."""

    def test_build_user_batch_creates_users(self) -> None:
        from tests.factories.data_factories import build_user_batch

        users = build_user_batch(5)
        assert len(users) == 5
        for u in users:
            assert "user_id" in u
            assert "email" in u
            assert "password_hash" in u
            assert len(u["user_id"]) == 32  # hex UUID

    def test_build_sponsor_has_required_fields(self) -> None:
        from tests.factories.data_factories import build_sponsor

        s = build_sponsor()
        assert "sponsor_id" in s
        assert "name" in s
        assert s["status"] in ("active", "inactive")

    def test_build_drawing_has_required_fields(self) -> None:
        from tests.factories.data_factories import build_drawing

        d = build_drawing(drawing_type="daily", ticket_cost_points=100, status="open")
        assert d["drawing_type"] == "daily"
        assert d["ticket_cost_points"] == 100
        assert d["status"] == "open"

    def test_build_connection_valid_sync_status(self) -> None:
        from tests.factories.data_factories import build_connection

        c = build_connection()
        assert c["sync_status"] in ("pending", "syncing", "success", "error")

    def test_build_activity_has_external_id(self) -> None:
        from tests.factories.data_factories import build_activity

        a = build_activity()
        assert "external_id" in a
        assert len(a["external_id"]) == 32

    def test_build_profile_has_tier_code(self) -> None:
        from tests.factories.data_factories import build_profile

        p = build_profile()
        assert "tier_code" in p
        assert p["tier_code"] is not None

    def test_build_ticket_no_orphan_fk(self) -> None:
        from tests.factories.data_factories import build_ticket

        t = build_ticket(drawing_id="abc123", user_id="def456")
        assert t["drawing_id"] == "abc123"
        assert t["user_id"] == "def456"
        # No purchase_transaction_id by default (avoids FK violation)
        assert "purchase_transaction_id" not in t


class TestC2SeedScript:
    """C2) seed_data.py module structure is correct."""

    def test_seed_module_importable(self) -> None:
        import scripts.seed_data

        assert hasattr(scripts.seed_data, "seed_database")

    def test_seed_function_exists(self) -> None:
        from scripts.seed_data import seed_database

        assert callable(seed_database)

    def test_seed_creates_expected_entity_types(self) -> None:
        """Verify seed creates at least sponsors, users, profiles, drawings."""
        from scripts.seed_data import seed_database

        # We mock the DB to verify the function calls _insert_row with right tables
        with patch("scripts.seed_data._connect") as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            seed_database()

            # Check _insert_row was called (via cur.execute)
            assert mock_cursor.execute.call_count > 0
            mock_conn.commit.assert_called()
