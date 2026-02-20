"""Leaderboard service — ranking engine for FitTrack competition tiers.

Rankings are based on **points earned** (not balance) within a period.
Tie-breaking order:
  1. Earlier achievement of the point total
  2. More active days in period
  3. User ID (deterministic fallback)

Periods: daily, weekly, monthly, all-time.
All period boundaries use US Eastern (EST/EDT).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# US Eastern for period boundaries
EST = ZoneInfo("America/New_York")

# Leaderboard constants
LEADERBOARD_TOP_N = 100
LEADERBOARD_CONTEXT_WINDOW = 10  # ±10 positions around user
VALID_PERIODS = ("daily", "weekly", "monthly", "all_time")


class LeaderboardError(Exception):
    """Leaderboard service error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Period boundary helpers ─────────────────────────────────────────


def get_period_start(period: str, now: datetime | None = None) -> datetime:
    """Return the start of the current *period* in UTC.

    Period boundaries are defined in US Eastern time, then converted
    to UTC for database queries.
    """
    if now is None:
        now = datetime.now(tz=UTC)

    now_est = now.astimezone(EST)

    if period == "daily":
        start_est = now_est.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "weekly":
        # Monday 00:00 EST
        days_since_monday = now_est.weekday()
        start_est = now_est - timedelta(days=days_since_monday)
        start_est = start_est.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "monthly":
        start_est = now_est.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "all_time":
        # Epoch — include everything
        return datetime(2020, 1, 1, tzinfo=UTC)
    else:
        raise LeaderboardError(f"Invalid period: {period}")

    return start_est.astimezone(UTC)


def get_period_end(period: str, now: datetime | None = None) -> datetime:
    """Return the end of the current *period* (i.e. now) in UTC."""
    if now is None:
        now = datetime.now(tz=UTC)
    return now


# ── Ranking engine (pure function) ─────────────────────────────────


def compute_rankings(
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Sort users by points earned and apply tie-breaking rules.

    Each entry must contain:
      - user_id: str
      - points_earned: int (total points earned in period)
      - earliest_achievement: datetime | str | None
      - active_days: int
      - display_name: str | None
      - tier_code: str | None

    Returns a list with ``rank`` added to each entry, sorted 1..N.
    """

    def sort_key(entry: dict[str, Any]) -> tuple[int, Any, int, str]:
        pts = -(entry.get("points_earned", 0) or 0)

        # Tie-break 1: earliest achievement of the total
        ea = entry.get("earliest_achievement")
        if ea is None:
            ea_val = datetime.max.replace(tzinfo=UTC)
        elif isinstance(ea, str):
            try:
                ea_val = datetime.fromisoformat(ea)
            except ValueError:
                ea_val = datetime.max.replace(tzinfo=UTC)
        else:
            ea_val = ea
        if ea_val.tzinfo is None:
            ea_val = ea_val.replace(tzinfo=UTC)

        # Tie-break 2: more active days (descending → negate)
        active = -(entry.get("active_days", 0) or 0)

        # Tie-break 3: user_id (ascending, deterministic)
        uid = entry.get("user_id", "")

        return (pts, ea_val, active, uid)

    sorted_entries = sorted(entries, key=sort_key)

    ranked: list[dict[str, Any]] = []
    for i, entry in enumerate(sorted_entries, start=1):
        ranked_entry = dict(entry)
        ranked_entry["rank"] = i
        ranked.append(ranked_entry)

    return ranked


def extract_user_context(
    rankings: list[dict[str, Any]],
    user_id: str,
    window: int = LEADERBOARD_CONTEXT_WINDOW,
) -> dict[str, Any]:
    """Extract user's rank and surrounding ±window positions.

    Returns:
        {
            "user_rank": int | None,
            "user_entry": dict | None,
            "total_participants": int,
            "context": [entries around user],
        }
    """
    total = len(rankings)
    user_idx = None
    user_entry = None

    for i, entry in enumerate(rankings):
        if entry.get("user_id") == user_id:
            user_idx = i
            user_entry = entry
            break

    if user_idx is None:
        return {
            "user_rank": None,
            "user_entry": None,
            "total_participants": total,
            "context": [],
        }

    assert user_entry is not None
    start = max(0, user_idx - window)
    end = min(total, user_idx + window + 1)
    context = rankings[start:end]

    return {
        "user_rank": user_entry["rank"],
        "user_entry": user_entry,
        "total_participants": total,
        "context": context,
    }


# ── Leaderboard Service ────────────────────────────────────────────


class LeaderboardService:
    """Orchestrates leaderboard data retrieval, ranking computation,
    and caching.
    """

    def __init__(
        self,
        transaction_repo: Any,
        profile_repo: Any,
        activity_repo: Any,
        cache_service: Any | None = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.profile_repo = profile_repo
        self.activity_repo = activity_repo
        self.cache = cache_service

    def get_leaderboard(
        self,
        period: str,
        tier_code: str | None = None,
        page: int = 1,
        limit: int = LEADERBOARD_TOP_N,
    ) -> dict[str, Any]:
        """Get the leaderboard for a given period and optional tier.

        Checks cache first; falls back to live computation.
        """
        if period not in VALID_PERIODS:
            raise LeaderboardError(f"Invalid period: {period}")

        cache_key = f"leaderboard:{period}:{tier_code or 'global'}"

        # Try cache
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return self._paginate_cached(cached, page, limit)

        # Compute live
        rankings = self._compute_live(period, tier_code)

        # Cache the result
        if self.cache is not None:
            self.cache.set(cache_key, rankings, ttl=900)  # 15 min

        return self._paginate(rankings, page, limit, period, tier_code)

    def get_user_rank(
        self,
        user_id: str,
        period: str,
        tier_code: str | None = None,
    ) -> dict[str, Any]:
        """Get a specific user's rank and context within a leaderboard."""
        if period not in VALID_PERIODS:
            raise LeaderboardError(f"Invalid period: {period}")

        cache_key = f"leaderboard:{period}:{tier_code or 'global'}"

        rankings = None
        if self.cache is not None:
            rankings = self.cache.get(cache_key)

        if rankings is None:
            rankings = self._compute_live(period, tier_code)
            if self.cache is not None:
                self.cache.set(cache_key, rankings, ttl=900)

        context = extract_user_context(rankings, user_id)
        context["period"] = period
        context["tier_code"] = tier_code
        return context

    def invalidate_cache(
        self,
        period: str | None = None,
        tier_code: str | None = None,
    ) -> int:
        """Invalidate leaderboard cache entries.

        If period and tier_code are None, invalidate all.
        Returns number of keys invalidated.
        """
        if self.cache is None:
            return 0

        if period and tier_code:
            key = f"leaderboard:{period}:{tier_code}"
            return 1 if self.cache.delete(key) else 0

        # Invalidate all leaderboard keys
        return int(self.cache.delete_pattern("leaderboard:*"))

    # ── Private helpers ─────────────────────────────────────────────

    def _compute_live(
        self,
        period: str,
        tier_code: str | None,
    ) -> list[dict[str, Any]]:
        """Compute rankings from transaction and activity data."""
        start = get_period_start(period)
        end = get_period_end(period)

        # Get users in tier (or all users)
        if tier_code:
            profiles = self.profile_repo.find_by_tier_code(tier_code)
        else:
            profiles = self.profile_repo.find_all(limit=10000, offset=0)

        if not profiles:
            return []

        entries: list[dict[str, Any]] = []
        for profile in profiles:
            user_id = profile.get("user_id", "")
            if not user_id:
                continue

            # Sum earn transactions in period
            user_txns = self.transaction_repo.find_by_user_id(user_id)
            points_earned = 0
            earliest_achievement = None

            for txn in user_txns:
                if txn.get("transaction_type") != "earn":
                    continue
                created = txn.get("created_at")
                if created is None:
                    continue
                if isinstance(created, str):
                    try:
                        created = datetime.fromisoformat(created)
                    except ValueError:
                        continue
                if hasattr(created, "tzinfo") and created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                if start <= created <= end:
                    amount = txn.get("amount", 0) or 0
                    points_earned += amount
                    if earliest_achievement is None or created < earliest_achievement:
                        earliest_achievement = created

            # Count active days in period
            active_days = self._count_active_days(user_id, start, end)

            entries.append(
                {
                    "user_id": user_id,
                    "display_name": profile.get("display_name", ""),
                    "tier_code": profile.get("tier_code", ""),
                    "points_earned": points_earned,
                    "earliest_achievement": earliest_achievement,
                    "active_days": active_days,
                }
            )

        return compute_rankings(entries)

    def _count_active_days(
        self,
        user_id: str,
        start: datetime,
        end: datetime,
    ) -> int:
        """Count days with ≥30 minutes of activity in the period."""
        try:
            activities = self.activity_repo.find_by_user_and_date_range(user_id, start, end)
        except Exception:
            activities = []

        from fittrack.core.constants import ACTIVE_DAY_MIN_MINUTES

        day_minutes: dict[str, int] = {}
        for a in activities:
            created = a.get("start_time") or a.get("created_at")
            if created is None:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if hasattr(created, "tzinfo") and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            day_key = created.strftime("%Y-%m-%d")
            duration = a.get("duration_minutes", 0) or 0
            day_minutes[day_key] = day_minutes.get(day_key, 0) + duration

        return sum(1 for mins in day_minutes.values() if mins >= ACTIVE_DAY_MIN_MINUTES)

    def _paginate(
        self,
        rankings: list[dict[str, Any]],
        page: int,
        limit: int,
        period: str,
        tier_code: str | None,
    ) -> dict[str, Any]:
        total = len(rankings)
        offset = (page - 1) * limit
        items = rankings[offset : offset + limit]
        total_pages = max(1, (total + limit - 1) // limit)

        # Serialize datetimes
        for item in items:
            ea = item.get("earliest_achievement")
            if isinstance(ea, datetime):
                item["earliest_achievement"] = ea.isoformat()

        return {
            "period": period,
            "tier_code": tier_code,
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }

    def _paginate_cached(
        self,
        rankings: list[dict[str, Any]],
        page: int,
        limit: int,
    ) -> dict[str, Any]:
        """Paginate pre-computed cached rankings."""
        total = len(rankings)
        offset = (page - 1) * limit
        items = rankings[offset : offset + limit]
        total_pages = max(1, (total + limit - 1) // limit)
        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }
