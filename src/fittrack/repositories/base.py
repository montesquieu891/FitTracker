"""Base repository providing generic CRUD operations for Oracle DB."""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

try:
    import oracledb

    _HAS_ORACLEDB = True
except ImportError:  # pragma: no cover – unit tests run without oracledb
    _HAS_ORACLEDB = False

logger = logging.getLogger(__name__)

SLOW_QUERY_THRESHOLD_MS = 100  # Log queries slower than this


class BaseRepository:
    """Generic repository with CRUD operations using python-oracledb.

    All entity repositories extend this class and configure
    ``table_name`` and ``id_column``.
    """

    def __init__(
        self,
        pool: Any,
        table_name: str,
        id_column: str,
    ) -> None:
        self.pool = pool
        self.table_name = table_name
        self.id_column = id_column

    # ── helpers ──────────────────────────────────────────────────────

    def _acquire(self) -> Any:
        """Acquire a connection from the pool."""
        return self.pool.acquire()

    @staticmethod
    def _log_query(sql: str, elapsed_ms: float) -> None:
        """Log query timing; warn if above slow-query threshold."""
        if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "SLOW QUERY (%.1fms): %s",
                elapsed_ms,
                sql[:200],
            )
        else:
            logger.debug("Query (%.1fms): %s", elapsed_ms, sql[:200])

    @staticmethod
    def _generate_id() -> str:
        """Generate a new UUID string."""
        return uuid.uuid4().hex

    @staticmethod
    def _to_raw_id(entity_id: str) -> str | bytes:
        """Convert a 32-char hex ID to bytes for Oracle RAW column binding.

        python-oracledb binds plain strings as VARCHAR2, which doesn't
        reliably match RAW(16) columns in WHERE clauses.  Converting to
        ``bytes`` forces binding as DB_TYPE_RAW.
        """
        try:
            if len(entity_id) == 32:
                return bytes.fromhex(entity_id)
        except (ValueError, TypeError):
            pass
        return entity_id

    @staticmethod
    def _convert_row(row: dict[str, Any]) -> dict[str, Any]:
        """Convert Oracle-specific types for JSON serialization.

        * ``bytes`` (RAW columns) → hex string
        * ``oracledb.LOB`` (CLOB/BLOB columns) → str / bytes
        """
        converted: dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, bytes):
                converted[k] = v.hex()
            elif _HAS_ORACLEDB and isinstance(v, oracledb.LOB):
                converted[k] = v.read()
            else:
                converted[k] = v
        return converted

    def _build_where(
        self,
        filters: dict[str, Any],
        prefix: str = "w_",
    ) -> tuple[str, dict[str, Any]]:
        """Build a WHERE clause and bind‑param dict from *filters*.

        Returns ("WHERE col1 = :w_col1 AND col2 = :w_col2", {":w_col1": v1, …}).
        """
        if not filters:
            return "", {}
        clauses: list[str] = []
        params: dict[str, Any] = {}
        for col, val in filters.items():
            bind_name = f"{prefix}{col}"
            clauses.append(f"{col} = :{bind_name}")
            params[bind_name] = val
        return "WHERE " + " AND ".join(clauses), params

    # ── read ─────────────────────────────────────────────────────────

    def find_by_id(self, entity_id: str) -> dict[str, Any] | None:
        """Return a single row by primary key, or ``None``."""
        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                sql = f"SELECT * FROM {self.table_name} WHERE {self.id_column} = :id"
                start = time.perf_counter()
                cur.execute(sql, {"id": self._to_raw_id(entity_id)})
                columns = [col[0].lower() for col in (cur.description or [])]
                row = cur.fetchone()
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                if row is None:
                    return None
                return self._convert_row(dict(zip(columns, row, strict=True)))
        finally:
            conn.close()

    def find_all(
        self,
        limit: int = 20,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Return paginated rows, optionally filtered."""
        where_clause, params = self._build_where(filters or {})
        sql = (
            f"SELECT * FROM {self.table_name} {where_clause} "
            f"OFFSET :off ROWS FETCH NEXT :lim ROWS ONLY"
        )
        params["off"] = offset
        params["lim"] = limit

        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                start = time.perf_counter()
                cur.execute(sql, params)
                columns = [col[0].lower() for col in (cur.description or [])]
                rows = [
                    self._convert_row(dict(zip(columns, row, strict=True)))
                    for row in cur.fetchall()
                ]
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                return rows
        finally:
            conn.close()

    def find_by_field(
        self,
        field: str,
        value: Any,
    ) -> list[dict[str, Any]]:
        """Return all rows matching a single field value."""
        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                sql = f"SELECT * FROM {self.table_name} WHERE {field} = :val"
                start = time.perf_counter()
                cur.execute(sql, {"val": value})
                columns = [col[0].lower() for col in (cur.description or [])]
                rows = [
                    self._convert_row(dict(zip(columns, row, strict=True)))
                    for row in cur.fetchall()
                ]
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                return rows
        finally:
            conn.close()

    def count(self, filters: dict[str, Any] | None = None) -> int:
        """Return row count, optionally filtered."""
        where_clause, params = self._build_where(filters or {})
        sql = f"SELECT COUNT(*) AS cnt FROM {self.table_name} {where_clause}"

        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                start = time.perf_counter()
                cur.execute(sql, params)
                row = cur.fetchone()
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                return int(row[0]) if row else 0
        finally:
            conn.close()

    # ── write ────────────────────────────────────────────────────────

    def create(
        self,
        data: dict[str, Any],
        new_id: str | None = None,
    ) -> str:
        """Insert a new row and return its ID.

        The ID is either supplied via *new_id* or auto‑generated.
        """
        if new_id is None:
            new_id = self._generate_id()

        all_data = {self.id_column: new_id, **data}
        columns = ", ".join(all_data.keys())
        placeholders = ", ".join(f":{k}" for k in all_data)
        sql = f"INSERT INTO {self.table_name} ({columns}) VALUES ({placeholders})"

        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                start = time.perf_counter()
                cur.execute(sql, all_data)
                conn.commit()
                self._log_query(sql, (time.perf_counter() - start) * 1000)
            return new_id
        finally:
            conn.close()

    def update(self, entity_id: str, data: dict[str, Any]) -> int:
        """Update a row by primary key. Returns rows affected."""
        if not data:
            raise ValueError("No data provided for update")

        set_clause = ", ".join(f"{k} = :s_{k}" for k in data)
        params: dict[str, Any] = {f"s_{k}": v for k, v in data.items()}
        params["id"] = self._to_raw_id(entity_id)

        sql = f"UPDATE {self.table_name} SET {set_clause} WHERE {self.id_column} = :id"

        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                start = time.perf_counter()
                cur.execute(sql, params)
                conn.commit()
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                return int(cur.rowcount)
        finally:
            conn.close()

    def delete(self, entity_id: str) -> int:
        """Delete a row by primary key. Returns rows affected."""
        sql = f"DELETE FROM {self.table_name} WHERE {self.id_column} = :id"

        conn = self._acquire()
        try:
            with conn.cursor() as cur:
                start = time.perf_counter()
                cur.execute(sql, {"id": self._to_raw_id(entity_id)})
                conn.commit()
                self._log_query(sql, (time.perf_counter() - start) * 1000)
                return int(cur.rowcount)
        finally:
            conn.close()
