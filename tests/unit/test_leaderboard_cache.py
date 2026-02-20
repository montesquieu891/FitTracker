"""Tests for CacheService — in-memory fallback and Redis mock paths."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from fittrack.services.cache import CacheService

# ── In-memory fallback (no Redis) ──────────────────────────────────


class TestCacheServiceInMemory:
    """CacheService with redis_client=None falls back to dict-based store."""

    def test_is_not_redis(self):
        cache = CacheService()
        assert cache.is_redis is False

    def test_get_miss_returns_none(self):
        cache = CacheService()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        cache = CacheService()
        assert cache.set("key1", {"data": 42})
        assert cache.get("key1") == {"data": 42}

    def test_set_overwrites(self):
        cache = CacheService()
        cache.set("key1", "v1")
        cache.set("key1", "v2")
        assert cache.get("key1") == "v2"

    def test_delete_existing_key(self):
        cache = CacheService()
        cache.set("key1", "value")
        assert cache.delete("key1") is True
        assert cache.get("key1") is None

    def test_delete_missing_key(self):
        cache = CacheService()
        assert cache.delete("nope") is False

    def test_exists_true(self):
        cache = CacheService()
        cache.set("key1", 1)
        assert cache.exists("key1") is True

    def test_exists_false(self):
        cache = CacheService()
        assert cache.exists("nope") is False

    def test_flush_clears_all(self):
        cache = CacheService()
        cache.set("a", 1)
        cache.set("b", 2)
        cache.flush()
        assert cache.get("a") is None
        assert cache.get("b") is None

    def test_delete_pattern_trailing_star(self):
        cache = CacheService()
        cache.set("leaderboard:daily:M-18-29-BEG", [1])
        cache.set("leaderboard:weekly:M-18-29-BEG", [2])
        cache.set("other:key", [3])
        count = cache.delete_pattern("leaderboard:*")
        assert count == 2
        assert cache.get("other:key") == [3]

    def test_delete_pattern_no_match(self):
        cache = CacheService()
        cache.set("a", 1)
        count = cache.delete_pattern("zzz:*")
        assert count == 0

    def test_set_returns_true(self):
        cache = CacheService()
        assert cache.set("k", "v") is True


# ── Leaderboard convenience methods ────────────────────────────────


class TestCacheLeaderboardConvenience:
    def test_set_and_get_leaderboard(self):
        cache = CacheService()
        rankings = [{"user_id": "u1", "rank": 1, "points_earned": 100}]
        cache.set_leaderboard("daily", "M-18-29-BEG", rankings)
        result = cache.get_leaderboard("daily", "M-18-29-BEG")
        assert result == rankings

    def test_get_leaderboard_miss(self):
        cache = CacheService()
        assert cache.get_leaderboard("daily", "M-18-29-BEG") is None

    def test_global_leaderboard(self):
        cache = CacheService()
        rankings = [{"user_id": "u1"}]
        cache.set_leaderboard("weekly", None, rankings)
        assert cache.get_leaderboard("weekly", None) == rankings
        assert cache.exists("leaderboard:weekly:global")

    def test_invalidate_leaderboards(self):
        cache = CacheService()
        cache.set_leaderboard("daily", "M-18-29-BEG", [])
        cache.set_leaderboard("weekly", "F-30-39-INT", [])
        cache.set("user:123", "data")
        count = cache.invalidate_leaderboards()
        assert count == 2
        assert cache.exists("user:123")

    def test_custom_ttl(self):
        cache = CacheService()
        # In-memory doesn't enforce TTL, but method should accept it
        assert cache.set_leaderboard("daily", "M-18-29-BEG", [], ttl=60) is True


# ── Redis-backed (mocked) ──────────────────────────────────────────


class TestCacheServiceRedis:
    """CacheService with a mock Redis client exercises the Redis code path."""

    @pytest.fixture
    def mock_redis(self):
        r = MagicMock()
        r.get.return_value = None
        r.exists.return_value = 0
        return r

    @pytest.fixture
    def cache(self, mock_redis: MagicMock):
        return CacheService(redis_client=mock_redis)

    def test_is_redis(self, cache: CacheService):
        assert cache.is_redis is True

    def test_get_calls_redis(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.get.return_value = '{"k": 1}'
        result = cache.get("key1")
        mock_redis.get.assert_called_once_with("key1")
        assert result == {"k": 1}

    def test_get_miss(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.get.return_value = None
        assert cache.get("miss") is None

    def test_get_handles_error(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.get.side_effect = ConnectionError("redis down")
        assert cache.get("key") is None

    def test_set_calls_setex(self, cache: CacheService, mock_redis: MagicMock):
        result = cache.set("key", {"a": 1}, ttl=600)
        assert result is True
        mock_redis.setex.assert_called_once()
        args = mock_redis.setex.call_args
        assert args[0][0] == "key"
        assert args[0][1] == 600

    def test_set_handles_error(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.setex.side_effect = ConnectionError("redis down")
        assert cache.set("key", "val") is False

    def test_delete_calls_redis(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.delete.return_value = 1
        assert cache.delete("key") is True
        mock_redis.delete.assert_called_once_with("key")

    def test_delete_missing(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.delete.return_value = 0
        assert cache.delete("nope") is False

    def test_delete_handles_error(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.delete.side_effect = ConnectionError("down")
        assert cache.delete("k") is False

    def test_exists_calls_redis(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.exists.return_value = 1
        assert cache.exists("key") is True

    def test_exists_handles_error(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.exists.side_effect = ConnectionError("down")
        assert cache.exists("key") is False

    def test_flush_calls_flushdb(self, cache: CacheService, mock_redis: MagicMock):
        cache.flush()
        mock_redis.flushdb.assert_called_once()

    def test_delete_pattern_uses_scan(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.scan.return_value = (0, [b"leaderboard:daily:T1"])
        mock_redis.delete.return_value = 1
        count = cache.delete_pattern("leaderboard:*")
        assert count == 1
        mock_redis.scan.assert_called_once()

    def test_delete_pattern_handles_error(self, cache: CacheService, mock_redis: MagicMock):
        mock_redis.scan.side_effect = ConnectionError("down")
        assert cache.delete_pattern("leaderboard:*") == 0
