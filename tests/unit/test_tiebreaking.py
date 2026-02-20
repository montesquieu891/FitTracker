"""Tests for tie-breaking scenarios in leaderboard rankings."""

from __future__ import annotations

from datetime import UTC, datetime

from fittrack.services.leaderboard import compute_rankings


class TestTieBreakingScenarios:
    """Exhaustive tests for the three-level tie-breaking system:
    1. Earliest achievement of the point total
    2. More active days in period
    3. User ID (deterministic fallback)
    """

    def test_points_always_primary(self):
        """Higher points always wins, regardless of other factors."""
        entries = [
            {
                "user_id": "z_late",
                "points_earned": 500,
                "earliest_achievement": datetime(2026, 1, 20, tzinfo=UTC),
                "active_days": 1,
            },
            {
                "user_id": "a_early",
                "points_earned": 100,
                "earliest_achievement": datetime(2026, 1, 1, tzinfo=UTC),
                "active_days": 7,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "z_late"

    def test_tie_break_1_earliest_wins(self):
        """Same points → earlier achievement wins."""
        t1 = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": "u_late",
                "points_earned": 300,
                "earliest_achievement": t2,
                "active_days": 5,
            },
            {
                "user_id": "u_early",
                "points_earned": 300,
                "earliest_achievement": t1,
                "active_days": 5,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u_early"
        assert ranked[1]["user_id"] == "u_late"

    def test_tie_break_1_by_seconds(self):
        """Even a one-second difference matters."""
        t1 = datetime(2026, 1, 15, 10, 0, 0, tzinfo=UTC)
        t2 = datetime(2026, 1, 15, 10, 0, 1, tzinfo=UTC)
        entries = [
            {
                "user_id": "u2",
                "points_earned": 200,
                "earliest_achievement": t2,
                "active_days": 3,
            },
            {
                "user_id": "u1",
                "points_earned": 200,
                "earliest_achievement": t1,
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u1"

    def test_tie_break_2_active_days(self):
        """Same points + same earliest → more active days wins."""
        t = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": "u_lazy",
                "points_earned": 200,
                "earliest_achievement": t,
                "active_days": 2,
            },
            {
                "user_id": "u_active",
                "points_earned": 200,
                "earliest_achievement": t,
                "active_days": 7,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u_active"

    def test_tie_break_3_user_id(self):
        """Same everything → alphabetical user_id wins."""
        t = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": "charlie",
                "points_earned": 200,
                "earliest_achievement": t,
                "active_days": 3,
            },
            {
                "user_id": "alice",
                "points_earned": 200,
                "earliest_achievement": t,
                "active_days": 3,
            },
            {
                "user_id": "bob",
                "points_earned": 200,
                "earliest_achievement": t,
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "alice"
        assert ranked[1]["user_id"] == "bob"
        assert ranked[2]["user_id"] == "charlie"

    def test_cascade_all_three_levels(self):
        """Four users with decreasing specificity of tie-break."""
        t_early = datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
        t_late = datetime(2026, 1, 15, 16, 0, tzinfo=UTC)
        entries = [
            # Wins on points (400)
            {
                "user_id": "d",
                "points_earned": 400,
                "earliest_achievement": t_late,
                "active_days": 1,
            },
            # Wins tie-break 1 (300 pts, earliest)
            {
                "user_id": "c",
                "points_earned": 300,
                "earliest_achievement": t_early,
                "active_days": 2,
            },
            # Loses tie-break 1, wins tie-break 2 (300 pts, later, more days)
            {
                "user_id": "b",
                "points_earned": 300,
                "earliest_achievement": t_late,
                "active_days": 5,
            },
            # Loses all, wins tie-break 3 (300 pts, later, same days, alpha)
            {
                "user_id": "a",
                "points_earned": 300,
                "earliest_achievement": t_late,
                "active_days": 5,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "d"  # 400 pts
        assert ranked[1]["user_id"] == "c"  # 300 pts, earliest
        assert ranked[2]["user_id"] == "a"  # 300 pts, late, 5 days, alpha 'a'
        assert ranked[3]["user_id"] == "b"  # 300 pts, late, 5 days, alpha 'b'

    def test_none_vs_set_earliest(self):
        """User with no earliest_achievement loses to one who has it."""
        entries = [
            {
                "user_id": "u_has",
                "points_earned": 100,
                "earliest_achievement": datetime(2026, 1, 15, tzinfo=UTC),
                "active_days": 3,
            },
            {
                "user_id": "u_none",
                "points_earned": 100,
                "earliest_achievement": None,
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u_has"

    def test_zero_points_ordering(self):
        """Users with zero points are still ordered by tie-break rules."""
        entries = [
            {"user_id": "b", "points_earned": 0, "active_days": 2},
            {"user_id": "a", "points_earned": 0, "active_days": 5},
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "a"  # More active days

    def test_many_way_tie(self):
        """20 users with identical points/time → sorted by user_id."""
        t = datetime(2026, 1, 15, 10, 0, tzinfo=UTC)
        entries = [
            {
                "user_id": f"user_{i:02d}",
                "points_earned": 100,
                "earliest_achievement": t,
                "active_days": 3,
            }
            for i in range(20)
        ]
        ranked = compute_rankings(entries)
        user_ids = [r["user_id"] for r in ranked]
        assert user_ids == sorted(user_ids)

    def test_ranks_are_sequential(self):
        """Ranks must be 1, 2, 3, ... N with no gaps."""
        entries = [
            {"user_id": f"u{i}", "points_earned": i * 10}
            for i in range(10)
        ]
        ranked = compute_rankings(entries)
        ranks = [r["rank"] for r in ranked]
        assert ranks == list(range(1, 11))

    def test_string_iso_datetime(self):
        """ISO string timestamps should be parsed correctly."""
        entries = [
            {
                "user_id": "u1",
                "points_earned": 100,
                "earliest_achievement": "2026-01-15T10:00:00+00:00",
                "active_days": 3,
            },
            {
                "user_id": "u2",
                "points_earned": 100,
                "earliest_achievement": "2026-01-15T08:00:00+00:00",
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"

    def test_naive_datetime_treated_as_utc(self):
        """Naive datetimes (no tz) should be handled without error."""
        entries = [
            {
                "user_id": "u1",
                "points_earned": 100,
                "earliest_achievement": datetime(2026, 1, 15, 12, 0),
                "active_days": 3,
            },
            {
                "user_id": "u2",
                "points_earned": 100,
                "earliest_achievement": datetime(2026, 1, 15, 8, 0),
                "active_days": 3,
            },
        ]
        ranked = compute_rankings(entries)
        assert ranked[0]["user_id"] == "u2"

    def test_missing_fields_default_safely(self):
        """Entries with missing optional fields shouldn't crash."""
        entries = [
            {"user_id": "u1", "points_earned": 100},
            {"user_id": "u2"},
        ]
        ranked = compute_rankings(entries)
        assert len(ranked) == 2
        assert ranked[0]["user_id"] == "u1"
