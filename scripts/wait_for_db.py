"""Wait for Oracle database to become available, then run migrations.

Usage:
    python -m scripts.wait_for_db [--timeout 300]
"""

from __future__ import annotations

import logging
import os
import time

import oracledb

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def wait_for_db(
    dsn: str,
    user: str,
    password: str,
    timeout: int = 300,
    interval: int = 5,
) -> oracledb.Connection:
    """Block until Oracle accepts connections, then return a connection."""
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            conn = oracledb.connect(user=user, password=password, dsn=dsn)
            logger.info("Connected to Oracle on attempt %d", attempt)
            return conn
        except oracledb.Error as exc:
            logger.info(
                "Attempt %d failed (%s), retrying in %ds...", attempt, exc, interval
            )
            time.sleep(interval)

    msg = f"Could not connect to Oracle at {dsn} within {timeout}s"
    raise TimeoutError(msg)


def main() -> None:
    """Wait for DB, run migrations, optionally seed."""
    dsn = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
    user = os.getenv("ORACLE_USER", "fittrack")
    password = os.getenv("ORACLE_PASSWORD", "FitTrack_Dev_2026!")
    timeout = int(os.getenv("DB_WAIT_TIMEOUT", "300"))

    conn = wait_for_db(dsn, user, password, timeout)

    from scripts.migrations import run_migrations

    actions = run_migrations(conn)
    if actions:
        logger.info("Migrations applied: %s", actions)
    else:
        logger.info("No pending migrations")

    conn.close()
    logger.info("Database ready!")


if __name__ == "__main__":
    main()
