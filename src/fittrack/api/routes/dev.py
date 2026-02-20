"""Dev-only routes — /api/v1/dev (disabled in production)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/dev", tags=["dev"])
logger = logging.getLogger(__name__)


def _get_pool(request: Request) -> Any:
    """Get DB pool from app state, or None if unavailable."""
    return getattr(request.app.state, "db_pool", None)


@router.post("/seed", status_code=201)
def seed_database(request: Request) -> dict[str, Any]:
    """Seed the database with synthetic data."""
    pool = _get_pool(request)
    if pool is None:
        logger.info("Dev seed endpoint called (no DB pool — mock response)")
        return {
            "message": "Database seeded successfully",
            "detail": {
                "users": 25,
                "profiles": 25,
                "activities": 375,
                "drawings": 4,
            },
        }

    from scripts.seed_data import seed_database as run_seed

    run_seed()
    return {
        "message": "Database seeded successfully",
        "detail": "Seeded via seed_data script",
    }


@router.post("/reset")
def reset_database(request: Request) -> dict[str, Any]:
    """Reset the database — drop and recreate all tables."""
    pool = _get_pool(request)
    if pool is None:
        logger.info("Dev reset endpoint called (no DB pool — mock response)")
        return {
            "message": "Database reset successfully",
            "detail": {"tables_truncated": 10},
        }

    from fittrack.core.database import get_connection
    from scripts.migrations import drop_all_tables, run_migrations

    conn = get_connection()
    try:
        drop_actions = drop_all_tables(conn)
        create_actions = run_migrations(conn)
        return {
            "message": "Database reset successfully",
            "detail": {
                "dropped": drop_actions,
                "created": create_actions,
            },
        }
    finally:
        conn.close()


@router.post("/migrate")
def run_migrate(request: Request) -> dict[str, Any]:
    """Run pending database migrations."""
    pool = _get_pool(request)
    if pool is None:
        # Try to init the pool now
        try:
            import oracledb

            settings = request.app.state.settings
            pool = oracledb.create_pool(
                user=settings.oracle_user,
                password=settings.oracle_password,
                dsn=settings.oracle_dsn,
                min=settings.oracle_pool_min,
                max=settings.oracle_pool_max,
                increment=settings.oracle_pool_increment,
            )
            request.app.state.db_pool = pool
            # Also update the module-level pool
            import fittrack.core.database as db_mod

            db_mod._pool = pool
            logger.info("DB pool initialized via /migrate endpoint")
        except Exception as exc:
            return {"message": f"Cannot connect to database: {exc}"}

    from fittrack.core.database import get_connection
    from scripts.migrations import run_migrations

    conn = get_connection()
    try:
        actions = run_migrations(conn)
        return {
            "message": "Migrations complete",
            "detail": {"actions": actions},
        }
    finally:
        conn.close()


@router.get("/tables")
def list_tables(request: Request) -> dict[str, Any]:
    """List all tables in the current schema."""
    pool = _get_pool(request)
    if pool is None:
        return {"tables": [], "message": "No database connection"}

    from fittrack.core.database import get_connection

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM user_tables ORDER BY table_name"
            )
            tables = [row[0] for row in cur.fetchall()]
        return {"tables": tables, "count": len(tables)}
    finally:
        conn.close()
