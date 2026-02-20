"""Leaderboard worker — periodic recalculation of cached rankings.

Designed to run every 15 minutes (matching SYNC_INTERVAL_MINUTES).
Precomputes rankings for every active tier × period combination
and pushes them into the cache so API reads are instant.
"""

from __future__ import annotations

import logging
from typing import Any

from fittrack.services.leaderboard import VALID_PERIODS, LeaderboardService

logger = logging.getLogger(__name__)


class LeaderboardWorkerResult:
    """Result of a single worker run."""

    def __init__(self) -> None:
        self.tiers_processed: int = 0
        self.periods_processed: int = 0
        self.entries_cached: int = 0
        self.errors: list[str] = []
        self.success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "tiers_processed": self.tiers_processed,
            "periods_processed": self.periods_processed,
            "entries_cached": self.entries_cached,
            "errors": self.errors,
            "success": self.success,
        }


class LeaderboardWorker:
    """Batch worker that precomputes leaderboards for all tier/period combos.

    Usage::

        worker = LeaderboardWorker(leaderboard_service, profile_repo)
        result = worker.run()
    """

    def __init__(
        self,
        leaderboard_service: LeaderboardService,
        profile_repo: Any,
        cache_service: Any | None = None,
    ) -> None:
        self.leaderboard_service = leaderboard_service
        self.profile_repo = profile_repo
        self.cache = cache_service

    def run(self) -> dict[str, Any]:
        """Recompute and cache leaderboards for every active tier."""
        result = LeaderboardWorkerResult()

        # Discover active tier codes
        active_tiers = self._get_active_tiers()
        logger.info(
            "Leaderboard worker: %d active tiers to process", len(active_tiers)
        )

        # Also compute the global (no tier) leaderboard
        all_tier_codes: list[str | None] = [None, *active_tiers]

        for tier_code in all_tier_codes:
            result.tiers_processed += 1
            for period in VALID_PERIODS:
                try:
                    # _compute_live bypasses cache; we store the result
                    rankings = self.leaderboard_service._compute_live(
                        period, tier_code
                    )
                    result.periods_processed += 1
                    result.entries_cached += len(rankings)

                    # Push to cache
                    if self.cache is not None:
                        self.cache.set_leaderboard(
                            period, tier_code, rankings, ttl=900
                        )
                except Exception as e:
                    msg = f"Error computing {period}/{tier_code}: {e}"
                    logger.error(msg, exc_info=True)
                    result.errors.append(msg)
                    result.success = False

        logger.info(
            "Leaderboard worker complete: %d tiers, %d periods, %d entries",
            result.tiers_processed,
            result.periods_processed,
            result.entries_cached,
        )
        return result.to_dict()

    def _get_active_tiers(self) -> list[str]:
        """Return tier codes that have at least one profile."""
        from fittrack.core.constants import ALL_TIER_CODES

        active: list[str] = []
        for code in ALL_TIER_CODES:
            try:
                profiles = self.profile_repo.find_by_tier_code(code)
                if profiles:
                    active.append(code)
            except Exception:
                # If query fails, include the tier to be safe
                active.append(code)
        return active
