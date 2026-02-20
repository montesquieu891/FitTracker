"""Tests for leaderboard service — ranking engine, periods, tie-breaking."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fittrack.services.leaderboard import (
    EST,
    LeaderboardError,
    LeaderboardService,
    compute_rankings,
    extract_user_context,
    get_period_end,
    get_period_start,
)

# ── Period boundary helpers ─────────────────────────────────────────


class TestGetPeriodStart:
    def test_daily_midnight_est(self):
        # 2026-01-15 10:30 UTC → EST = 05:30 → start = 05:00 UTC (midnight EST)
        now = datetime(2026, 1, 15, 10, 30, tzinfo=UTC)
        start = get_period_start("daily", now)
        assert start.tzinfo is not None
        # Start should be midnight EST on Jan 15 → 05:00 UTC
        start_est = start.astimezone(EST)
        assert start_est.hour == 0
        assert start_est.minute == 0

    def test_weekly_monday(self):
        # 2026-01-15 is a Thursday
        now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        start = get_period_start("weekly", now)
        start_est = start.astimezone(EST)
        assert start_est.weekday() == 0  # Monday
        assert start_est.hour == 0

    def test_monthly_first(self):
        now = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
        start = get_period_start("monthly", now)
        start_est = start.astimezone(EST)
        assert start_est.day == 1
        assert start_est.hour == 0

    def test_all_time(self):
        start = get_period_start("all_time")
        assert start.year == 2020

    def test_invalid_period_raises(self):
        with pytest.raises(LeaderboardError, match="Invalid period"):
            get_period_start("hourly")


class TestGetPeriodEnd:
    def test_returns_now(self):
        now = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        end = get_period_end("daily", now)
        assert end == now

    def test_defaults_to_now(self):
        end = get_period_end("daily")
        assert end.tzinfo is not None
        assert (datetime.now(tz=UTC) - end).total_seconds() < 2


# ── compute_rankings ───────────────────────────────────────────────


class TestComputeRankings:
    def test_sort_by_points_descending(self):
        entries = [
            {"user_id": "u1", "points_earned": 100, "active_days": 3},
            {"user_id": "u2", "points_earned": 300, "active_days": 5},
            {"user_id": "u3", "points_earned": 200, "active_days": 4},
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"
        assert ranked[0]["rank"] == 1
        assert ranked[1]["user_id"] == "u3"
        assert ranked[1]["rank"] == 2
        assert ranked[2]["user_id"] == "u1"
        assert ranked[2]["rank"] == 3

    def test_tie_break_earliest_achievement(self):
        entries = [
            {
                "user_id": "u1",
                "points_earned": 200,
                "earliest_achievement": datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
                "active_days": 3,
            },
            {
                "user_id": "u2",
                "points_earned": 200,
                "earliest_achievement": datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"  # Earlier achievement wins
        assert ranked[1]["user_id"] == "u1"

    def test_tie_break_more_active_days(self):
        ea = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": "u1",
                "points_earned": 200,
                "earliest_achievement": ea,
                "active_days": 3,
            },
            {
                "user_id": "u2",
                "points_earned": 200,
                "earliest_achievement": ea,
                "active_days": 5,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"  # More active days wins

    def test_tie_break_user_id(self):
        ea = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": "u_beta",
                "points_earned": 200,
                "earliest_achievement": ea,
                "active_days": 3,
            },
            {
                "user_id": "u_alpha",
                "points_earned": 200,
                "earliest_achievement": ea,
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u_alpha"  # Alphabetical user_id

    def test_empty_list(self):
        assert compute_rankings([]) == []

    def test_single_entry(self):
        entries = [{"user_id": "u1", "points_earned": 100}]
        ranked = compute_rankings(entries)
        assert len(ranked) == 1
        assert ranked[0]["rank"] == 1

    def test_zero_points(self):
        entries = [
            {"user_id": "u1", "points_earned": 0},
            {"user_id": "u2", "points_earned": 50},
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"
        assert ranked[1]["user_id"] == "u1"

    def test_none_earliest_achievement(self):
        """Users with no earliest_achievement sort last among ties."""
        entries = [
            {"user_id": "u1", "points_earned": 100, "earliest_achievement": None},
            {
                "user_id": "u2",
                "points_earned": 100,
                "earliest_achievement": datetime(2026, 1, 15, 10, 0, tzinfo=UTC),
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"

    def test_string_earliest_achievement(self):
        entries = [
            {
                "user_id": "u1",
                "points_earned": 100,
                "earliest_achievement": "2026-01-15T12:00:00+00:00",
            },
            {
                "user_id": "u2",
                "points_earned": 100,
                "earliest_achievement": "2026-01-15T08:00:00+00:00",
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"

    def test_large_leaderboard(self):
        entries = [
            {"user_id": f"u{i}", "points_earned": i * 10, "active_days": i}
            for i in range(100)
        ]
        ranked = compute_rankings(entries)
        assert len(ranked) == 100
        assert ranked[0]["user_id"] == "u99"
        assert ranked[0]["rank"] == 1
        assert ranked[99]["user_id"] == "u0"
        assert ranked[99]["rank"] == 100


# ── extract_user_context ───────────────────────────────────────────


class TestExtractUserContext:
    def _make_rankings(self, count: int = 50) -> list[dict[str, Any]]:
        return [
            {"user_id": f"u{i}", "rank": i + 1, "points_earned": (count - i) * 10}
            for i in range(count)
        ]

    def test_user_in_middle(self):
        rankings = self._make_rankings(50)
        ctx = extract_user_context(rankings, "u25")
        assert ctx["user_rank"] == 26
        assert ctx["total_participants"] == 50
        assert len(ctx["context"]) == 21  # ±10 around position 25

    def test_user_at_top(self):
        rankings = self._make_rankings(50)
        ctx = extract_user_context(rankings, "u0")
        assert ctx["user_rank"] == 1
        # Context window: 0 to 10 (11 entries)
        assert len(ctx["context"]) == 11

    def test_user_at_bottom(self):
        rankings = self._make_rankings(50)
        ctx = extract_user_context(rankings, "u49")
        assert ctx["user_rank"] == 50
        # Context window: 39 to 49 (11 entries)
        assert len(ctx["context"]) == 11

    def test_user_not_found(self):
        rankings = self._make_rankings(10)
        ctx = extract_user_context(rankings, "nonexistent")
        assert ctx["user_rank"] is None
        assert ctx["user_entry"] is None
        assert ctx["context"] == []

    def test_small_leaderboard(self):
        rankings = self._make_rankings(3)
        ctx = extract_user_context(rankings, "u1")
        assert ctx["user_rank"] == 2
        assert len(ctx["context"]) == 3  # All entries in window

    def test_custom_window(self):
        rankings = self._make_rankings(50)
        ctx = extract_user_context(rankings, "u25", window=5)
        assert len(ctx["context"]) == 11  # ±5


# ── LeaderboardService ─────────────────────────────────────────────


class MockRepo:
    def __init__(self, data: list[dict[str, Any]] | None = None) -> None:
        self.data = data or []

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        return [d for d in self.data if d.get("user_id") == user_id]

    def find_by_tier_code(self, tier_code: str) -> list[dict[str, Any]]:
        return [d for d in self.data if d.get("tier_code") == tier_code]

    def find_all(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self.data[offset:offset + limit]

    def find_by_user_and_date_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        return [d for d in self.data if d.get("user_id") == user_id]


class MockCache:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any, ttl: int = 900) -> bool:
        self._store[key] = value
        return True

    def delete(self, key: str) -> bool:
        return self._store.pop(key, None) is not None

    def delete_pattern(self, pattern: str) -> int:
        import fnmatch
        keys = [k for k in self._store if fnmatch.fnmatch(k, pattern)]
        for k in keys:
            del self._store[k]
        return len(keys)


def _make_profiles(n: int = 5, tier: str = "M-18-29-BEG") -> list[dict[str, Any]]:
    return [
        {
            "user_id": f"u{i}",
            "display_name": f"User {i}",
            "tier_code": tier,
        }
        for i in range(n)
    ]


def _make_transactions(
    user_id: str,
    amount: int,
    created_at: datetime | None = None,
) -> list[dict[str, Any]]:
    return [
        {
            "user_id": user_id,
            "transaction_type": "earn",
            "amount": amount,
            "created_at": created_at or datetime.now(tz=UTC),
        }
    ]


class TestLeaderboardService:
    def _make_service(
        self,
        profiles: list[dict[str, Any]] | None = None,
        transactions: list[dict[str, Any]] | None = None,
        activities: list[dict[str, Any]] | None = None,
        cache: MockCache | None = None,
    ) -> LeaderboardService:
        return LeaderboardService(
            transaction_repo=MockRepo(transactions or []),
            profile_repo=MockRepo(profiles or []),
            activity_repo=MockRepo(activities or []),
            cache_service=cache,
        )

    def test_get_leaderboard_invalid_period(self):
        service = self._make_service()
        with pytest.raises(LeaderboardError, match="Invalid period"):
            service.get_leaderboard("hourly")

    def test_get_leaderboard_empty(self):
        service = self._make_service()
        result = service.get_leaderboard("daily", "M-18-29-BEG")
        assert result["items"] == []
        assert result["pagination"]["total_items"] == 0

    def test_get_leaderboard_with_data(self):
        profiles = _make_profiles(3)
        # Use period start to ensure transactions fall within the daily boundary
        from fittrack.services.leaderboard import get_period_start

        period_start = get_period_start("daily")
        txns = [
            *_make_transactions("u0", 100, period_start + timedelta(minutes=1)),
            *_make_transactions("u1", 300, period_start + timedelta(minutes=2)),
            *_make_transactions("u2", 200, period_start + timedelta(minutes=3)),
        ]
        service = self._make_service(profiles=profiles, transactions=txns)
        result = service.get_leaderboard("daily", "M-18-29-BEG")
        assert len(result["items"]) == 3
        assert result["items"][0]["user_id"] == "u1"  # 300 pts
        assert result["items"][0]["rank"] == 1

    def test_get_leaderboard_uses_cache(self):
        cache = MockCache()
        profiles = _make_profiles(2)
        service = self._make_service(profiles=profiles, cache=cache)

        # First call populates cache
        service.get_leaderboard("daily", "M-18-29-BEG")
        assert "leaderboard:daily:M-18-29-BEG" in cache._store

        # Second call uses cache (even if data changes)
        result = service.get_leaderboard("daily", "M-18-29-BEG")
        assert "items" in result

    def test_get_leaderboard_pagination(self):
        profiles = _make_profiles(10)
        now = datetime.now(tz=UTC)
        txns = []
        for i in range(10):
            txns.extend(_make_transactions(f"u{i}", (i + 1) * 10, now))
        service = self._make_service(profiles=profiles, transactions=txns)
        result = service.get_leaderboard("daily", "M-18-29-BEG", page=1, limit=5)
        assert len(result["items"]) == 5
        assert result["pagination"]["total_pages"] == 2

    def test_get_user_rank(self):
        profiles = _make_profiles(5)
        now = datetime.now(tz=UTC)
        txns = []
        for i in range(5):
            txns.extend(_make_transactions(f"u{i}", (i + 1) * 50, now))
        service = self._make_service(profiles=profiles, transactions=txns)
        result = service.get_user_rank("u2", "daily", "M-18-29-BEG")
        assert result["user_rank"] is not None
        assert result["total_participants"] == 5
        assert result["period"] == "daily"

    def test_get_user_rank_not_found(self):
        profiles = _make_profiles(3)
        service = self._make_service(profiles=profiles)
        result = service.get_user_rank("nonexistent", "daily", "M-18-29-BEG")
        assert result["user_rank"] is None

    def test_invalidate_cache_specific(self):
        cache = MockCache()
        cache._store["leaderboard:daily:M-18-29-BEG"] = []
        service = self._make_service(cache=cache)
        count = service.invalidate_cache("daily", "M-18-29-BEG")
        assert count == 1
        assert "leaderboard:daily:M-18-29-BEG" not in cache._store

    def test_invalidate_cache_all(self):
        cache = MockCache()
        cache._store["leaderboard:daily:M-18-29-BEG"] = []
        cache._store["leaderboard:weekly:M-18-29-BEG"] = []
        cache._store["other_key"] = "nope"
        service = self._make_service(cache=cache)
        count = service.invalidate_cache()
        assert count == 2
        assert "other_key" in cache._store  # Not a leaderboard key

    def test_invalidate_no_cache(self):
        service = self._make_service()
        assert service.invalidate_cache() == 0

    def test_all_time_includes_old_transactions(self):
        profiles = _make_profiles(1)
        old_txn = _make_transactions("u0", 500, datetime(2023, 6, 1, tzinfo=UTC))
        service = self._make_service(profiles=profiles, transactions=old_txn)
        result = service.get_leaderboard("all_time", "M-18-29-BEG")
        assert result["items"][0]["points_earned"] == 500

    def test_daily_excludes_old_transactions(self):
        profiles = _make_profiles(1)
        yesterday_txn = _make_transactions(
            "u0", 500, datetime.now(tz=UTC) - timedelta(days=2)
        )
        service = self._make_service(profiles=profiles, transactions=yesterday_txn)
        result = service.get_leaderboard("daily", "M-18-29-BEG")
        # Old transaction should not count in daily
        assert result["items"][0]["points_earned"] == 0

    def test_global_leaderboard_no_tier(self):
        profiles = [
            {"user_id": "u0", "display_name": "A", "tier_code": "M-18-29-BEG"},
            {"user_id": "u1", "display_name": "B", "tier_code": "F-30-39-INT"},
        ]
        now = datetime.now(tz=UTC)
        txns = [
            *_make_transactions("u0", 100, now),
            *_make_transactions("u1", 200, now),
        ]
        service = self._make_service(profiles=profiles, transactions=txns)
        result = service.get_leaderboard("daily", tier_code=None)
        assert len(result["items"]) == 2  # Both tiers included

    def test_count_active_days(self):
        profiles = _make_profiles(1)
        now = datetime.now(tz=UTC)
        activities = [
            {
                "user_id": "u0",
                "start_time": now - timedelta(hours=2),
                "duration_minutes": 45,
            },
            {
                "user_id": "u0",
                "start_time": now - timedelta(days=1, hours=2),
                "duration_minutes": 35,
            },
        ]
        txns = _make_transactions("u0", 100, now)
        service = self._make_service(
            profiles=profiles, transactions=txns, activities=activities
        )
        result = service.get_leaderboard("weekly", "M-18-29-BEG")
        assert result["items"][0]["active_days"] == 2
