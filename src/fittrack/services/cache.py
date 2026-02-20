"""Cache service — Redis-backed caching for FitTrack.

Used for leaderboard data, session management, and frequently-read values.
Falls back to an in-memory dict when Redis is unavailable (dev/test).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


class CacheService:
    """Unified caching interface backed by Redis or in-memory fallback.

    In production, *redis_client* is a ``redis.Redis`` instance.
    In tests / local dev without Redis, pass ``None`` to use an in-memory dict.
    """

    def __init__(self, redis_client: Any | None = None) -> None:
        self._redis = redis_client
        self._memory: dict[str, Any] = {}  # Fallback store

    @property
    def is_redis(self) -> bool:
        return self._redis is not None

    # ── Core operations ─────────────────────────────────────────────

    def get(self, key: str) -> Any | None:
        """Get a value by key. Returns ``None`` on miss or error."""
        if self._redis is not None:
            try:
                raw = self._redis.get(key)
                if raw is None:
                    return None
                return json.loads(raw)
            except Exception:
                logger.warning("Cache GET failed for %s", key, exc_info=True)
                return None
        return self._memory.get(key)

    def set(self, key: str, value: Any, ttl: int = 900) -> bool:
        """Set a value with TTL (seconds). Default 15 minutes."""
        if self._redis is not None:
            try:
                serialized = json.dumps(value, default=str)
                self._redis.setex(key, ttl, serialized)
                return True
            except Exception:
                logger.warning("Cache SET failed for %s", key, exc_info=True)
                return False
        self._memory[key] = value
        return True

    def delete(self, key: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        if self._redis is not None:
            try:
                return bool(self._redis.delete(key))
            except Exception:
                logger.warning("Cache DELETE failed for %s", key, exc_info=True)
                return False
        removed = key in self._memory
        self._memory.pop(key, None)
        return removed

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted.

        Uses Redis SCAN for production safety (no KEYS in prod).
        Falls back to dict key matching for in-memory store.
        """
        if self._redis is not None:
            try:
                count = 0
                cursor = 0
                while True:
                    cursor, keys = self._redis.scan(cursor=cursor, match=pattern, count=100)
                    if keys:
                        count += self._redis.delete(*keys)
                    if cursor == 0:
                        break
                return count
            except Exception:
                logger.warning("Cache DELETE_PATTERN failed for %s", pattern, exc_info=True)
                return 0

        # In-memory: simple glob-like matching (only supports trailing *)
        import fnmatch

        to_delete = [k for k in self._memory if fnmatch.fnmatch(k, pattern)]
        for k in to_delete:
            del self._memory[k]
        return len(to_delete)

    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if self._redis is not None:
            try:
                return bool(self._redis.exists(key))
            except Exception:
                return False
        return key in self._memory

    def flush(self) -> None:
        """Clear all cached data. Use with caution."""
        if self._redis is not None:
            try:
                self._redis.flushdb()
            except Exception:
                logger.warning("Cache FLUSH failed", exc_info=True)
        else:
            self._memory.clear()

    # ── Convenience for leaderboard ─────────────────────────────────

    def get_leaderboard(
        self,
        period: str,
        tier_code: str | None = None,
    ) -> list[dict[str, Any]] | None:
        """Shortcut to retrieve cached leaderboard rankings."""
        key = f"leaderboard:{period}:{tier_code or 'global'}"
        return self.get(key)

    def set_leaderboard(
        self,
        period: str,
        tier_code: str | None,
        rankings: list[dict[str, Any]],
        ttl: int = 900,
    ) -> bool:
        """Shortcut to cache leaderboard rankings."""
        key = f"leaderboard:{period}:{tier_code or 'global'}"
        return self.set(key, rankings, ttl=ttl)

    def invalidate_leaderboards(self) -> int:
        """Invalidate all leaderboard cache entries."""
        return self.delete_pattern("leaderboard:*")
