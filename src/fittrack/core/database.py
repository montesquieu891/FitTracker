"""Oracle database connection pool management."""

from __future__ import annotations

import logging
from typing import Any

import oracledb

from fittrack.core.config import Settings

logger = logging.getLogger(__name__)

# Module-level pool reference
_pool: oracledb.ConnectionPool | None = None


async def init_pool(settings: Settings) -> oracledb.ConnectionPool:
    """Create and return the Oracle connection pool."""
    global _pool
    if _pool is not None:
        return _pool

    logger.info("Creating Oracle connection pool: %s", settings.oracle_dsn)
    _pool = oracledb.create_pool(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
        min=settings.oracle_pool_min,
        max=settings.oracle_pool_max,
        increment=settings.oracle_pool_increment,
    )
    logger.info(
        "Oracle connection pool created (min=%d, max=%d)",
        settings.oracle_pool_min,
        settings.oracle_pool_max,
    )
    return _pool


async def close_pool() -> None:
    """Close the Oracle connection pool."""
    global _pool
    if _pool is not None:
        _pool.close(force=True)
        _pool = None
        logger.info("Oracle connection pool closed")


def get_pool() -> oracledb.ConnectionPool:
    """Get the current connection pool. Raises if not initialized."""
    if _pool is None:
        raise RuntimeError("Database pool not initialized. Call init_pool() first.")
    return _pool


def get_connection() -> oracledb.Connection:
    """Acquire a connection from the pool."""
    pool = get_pool()
    return pool.acquire()


def execute_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a SELECT query and return results as list of dicts."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            columns = [col[0].lower() for col in cur.description or []]
            rows = cur.fetchall()
            return [
                {
                    k: (
                        v.hex()
                        if isinstance(v, bytes)
                        else v.read()
                        if isinstance(v, oracledb.LOB)
                        else v
                    )
                    for k, v in dict(zip(columns, row, strict=True)).items()
                }
                for row in rows
            ]
    finally:
        conn.close()


def execute_dml(sql: str, params: dict[str, Any] | None = None) -> int:
    """Execute an INSERT/UPDATE/DELETE and return rows affected."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params or {})
            conn.commit()
            return int(cur.rowcount)
    finally:
        conn.close()


def execute_dml_returning(
    sql: str,
    params: dict[str, Any] | None = None,
    returning_cols: list[str] | None = None,
) -> dict[str, Any]:
    """Execute INSERT with RETURNING clause and return the inserted row as dict."""
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # Build out vars for RETURNING
            out_vars: dict[str, Any] = {}
            bind_params = dict(params or {})
            if returning_cols:
                for col in returning_cols:
                    var = cur.var(oracledb.STRING)
                    bind_params[f"out_{col}"] = var
                    out_vars[col] = var

            cur.execute(sql, bind_params)
            conn.commit()

            result: dict[str, Any] = {}
            for col, var in out_vars.items():
                val = var.getvalue()
                result[col] = val[0] if isinstance(val, list) and val else val
            return result
    finally:
        conn.close()
