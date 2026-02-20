"""Seed the database with synthetic test data.

Usage:
    python -m scripts.seed_data
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Add src to path so fittrack imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import oracledb

from fittrack.core.constants import (
    ALL_TIER_CODES,
    DRAWING_TYPES,
    DRAWING_TICKET_COSTS,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Re-use factories
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tests.factories.data_factories import (
    build_user_batch,
    build_profile,
    build_activity,
    build_connection,
    build_transaction,
    build_drawing,
    build_ticket,
    build_prize,
    build_sponsor,
    build_fulfillment,
)


def _connect() -> oracledb.Connection:
    """Connect to Oracle using environment variables."""
    dsn = os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1")
    user = os.getenv("ORACLE_USER", "fittrack")
    password = os.getenv("ORACLE_PASSWORD", "FitTrack_Dev_2026!")
    return oracledb.connect(user=user, password=password, dsn=dsn)


def _insert_row(cur: oracledb.Cursor, table: str, data: dict[str, Any]) -> None:
    """Insert a single row into a table."""
    import datetime

    # Convert non-primitive values appropriately for Oracle
    clean: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, (dict, list)):
            clean[k] = json.dumps(v)
        elif isinstance(v, (datetime.datetime, datetime.date)):
            # Keep native datetime objects — oracledb binds them correctly
            clean[k] = v
        elif v is None:
            clean[k] = None
        else:
            clean[k] = v

    columns = ", ".join(clean.keys())
    placeholders = ", ".join(f":{k}" for k in clean.keys())
    sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
    try:
        cur.execute(sql, clean)
    except oracledb.Error as e:
        logger.warning("Insert into %s failed: %s", table, e)


def seed_database() -> None:
    """Generate and insert synthetic data."""
    conn = _connect()
    cur = conn.cursor()
    logger.info("Connected to database, starting seed...")

    # ── 1. Sponsors ──
    sponsors = [build_sponsor() for _ in range(5)]
    for s in sponsors:
        _insert_row(cur, "sponsors", s)
    logger.info("Seeded %d sponsors", len(sponsors))

    # ── 2. Users ──
    users = build_user_batch(20, status="active", role="user")
    # Add 2 admins, 3 premium
    users.append(build_user_batch(1, role="admin", status="active")[0])
    users.append(build_user_batch(1, role="admin", status="active")[0])
    users.extend(build_user_batch(3, role="premium", status="active"))
    for u in users:
        _insert_row(cur, "users", u)
    logger.info("Seeded %d users", len(users))

    # ── 3. Profiles ──
    profiles = []
    for u in users:
        p = build_profile(user_id=u["user_id"])
        profiles.append(p)
        _insert_row(cur, "profiles", p)
    logger.info("Seeded %d profiles", len(profiles))

    # ── 4. Tracker Connections ──
    connections = []
    for u in users[:15]:  # 15 users have trackers
        c = build_connection(user_id=u["user_id"])
        connections.append(c)
        _insert_row(cur, "tracker_connections", c)
    logger.info("Seeded %d tracker connections", len(connections))

    # ── 5. Activities (5 per connected user) ──
    activities = []
    for c in connections:
        for _ in range(5):
            a = build_activity(user_id=c["user_id"])
            a["connection_id"] = c["connection_id"]
            activities.append(a)
            _insert_row(cur, "activities", a)
    logger.info("Seeded %d activities", len(activities))

    # ── 6. Point Transactions ──
    transactions = []
    for u in users:
        for _ in range(3):
            t = build_transaction(user_id=u["user_id"])
            transactions.append(t)
            _insert_row(cur, "point_transactions", t)
    logger.info("Seeded %d transactions", len(transactions))

    # ── 7. Drawings ──
    drawings = []
    for dtype in DRAWING_TYPES:
        d = build_drawing(
            drawing_type=dtype,
            ticket_cost_points=DRAWING_TICKET_COSTS[dtype],
            status="open",
        )
        drawings.append(d)
        _insert_row(cur, "drawings", d)
    logger.info("Seeded %d drawings", len(drawings))

    # ── 8. Prizes (2 per drawing) ──
    prizes = []
    for d in drawings:
        for rank in range(1, 3):
            p = build_prize(drawing_id=d["drawing_id"], rank=rank)
            p["sponsor_id"] = sponsors[rank % len(sponsors)]["sponsor_id"]
            prizes.append(p)
            _insert_row(cur, "prizes", p)
    logger.info("Seeded %d prizes", len(prizes))

    # ── 9. Tickets (3 users buy tickets to first drawing) ──
    tickets = []
    for u in users[:3]:
        t = build_ticket(drawing_id=drawings[0]["drawing_id"], user_id=u["user_id"])
        tickets.append(t)
        _insert_row(cur, "tickets", t)
    logger.info("Seeded %d tickets", len(tickets))

    # ── 10. Fulfillments (1 sample) ──
    if tickets and prizes:
        f = build_fulfillment(
            ticket_id=tickets[0]["ticket_id"],
            prize_id=prizes[0]["prize_id"],
            user_id=tickets[0]["user_id"],
        )
        _insert_row(cur, "prize_fulfillments", f)
        logger.info("Seeded 1 fulfillment")

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Seed complete!")


if __name__ == "__main__":
    seed_database()
