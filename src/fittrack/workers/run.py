"""CLI runner for FitTrack workers.

Usage:
    python -m fittrack.workers.run sync
    python -m fittrack.workers.run leaderboard
    python -m fittrack.workers.run drawing
"""

from __future__ import annotations

import argparse
import logging
import sys

from fittrack.core.logging import setup_logging

logger = logging.getLogger(__name__)


def _get_pool():
    """Create and return an oracledb connection pool."""
    import oracledb

    from fittrack.core.config import Settings

    settings = Settings()
    pool = oracledb.create_pool(
        user=settings.oracle_user,
        password=settings.oracle_password,
        dsn=settings.oracle_dsn,
        min=settings.oracle_pool_min,
        max=settings.oracle_pool_max,
        increment=settings.oracle_pool_increment,
    )
    return pool


def run_sync() -> int:
    """Run the sync worker once."""
    from fittrack.repositories.activity_repository import ActivityRepository
    from fittrack.repositories.connection_repository import ConnectionRepository
    from fittrack.repositories.daily_points_log_repository import DailyPointsLogRepository
    from fittrack.repositories.transaction_repository import TransactionRepository
    from fittrack.repositories.user_repository import UserRepository
    from fittrack.services.points import PointsService
    from fittrack.workers.sync_worker import SyncWorker

    try:
        pool = _get_pool()
    except Exception as exc:
        logger.error("Cannot connect to database: %s", exc)
        logger.info("Sync worker: no DB — exiting gracefully (0 connections processed)")
        return 0

    connection_repo = ConnectionRepository(pool=pool)
    activity_repo = ActivityRepository(pool=pool)
    user_repo = UserRepository(pool=pool)
    tx_repo = TransactionRepository(pool=pool)
    daily_log_repo = DailyPointsLogRepository(pool=pool)
    points_svc = PointsService(
        transaction_repo=tx_repo,
        user_repo=user_repo,
        activity_repo=activity_repo,
        daily_log_repo=daily_log_repo,
    )

    worker = SyncWorker(
        connection_repo=connection_repo,
        activity_repo=activity_repo,
        points_service=points_svc,
        providers={},  # No real OAuth providers in local dev
    )
    results = worker.run_batch()
    logger.info("Sync complete: %d connections processed", len(results))
    for r in results:
        status = "OK" if r.get("success") else "FAIL"
        logger.info(
            "  %s %s/%s — fetched=%s stored=%s",
            status,
            r.get("user_id", "?")[:8],
            r.get("provider", "?"),
            r.get("activities_fetched", 0),
            r.get("activities_stored", 0),
        )
    return 0


def run_leaderboard() -> int:
    """Run the leaderboard worker once."""
    from fittrack.repositories.activity_repository import ActivityRepository
    from fittrack.repositories.profile_repository import ProfileRepository
    from fittrack.repositories.transaction_repository import TransactionRepository
    from fittrack.services.leaderboard import LeaderboardService
    from fittrack.workers.leaderboard_worker import LeaderboardWorker

    try:
        pool = _get_pool()
    except Exception as exc:
        logger.error("Cannot connect to database: %s", exc)
        logger.info("Leaderboard worker: no DB — exiting gracefully")
        return 0

    tx_repo = TransactionRepository(pool=pool)
    profile_repo = ProfileRepository(pool=pool)
    activity_repo = ActivityRepository(pool=pool)

    lb_service = LeaderboardService(
        transaction_repo=tx_repo,
        profile_repo=profile_repo,
        activity_repo=activity_repo,
        cache_service=None,  # No Redis cache injection for CLI
    )

    worker = LeaderboardWorker(
        leaderboard_service=lb_service,
        profile_repo=profile_repo,
        cache_service=None,
    )
    result = worker.run()
    logger.info(
        "Leaderboard complete: tiers=%s periods=%s entries=%s",
        result.get("tiers_processed", 0),
        result.get("periods_processed", 0),
        result.get("entries_cached", 0),
    )
    return 0


def run_drawing() -> int:
    """Run the drawing worker once."""
    from fittrack.repositories.drawing_repository import DrawingRepository
    from fittrack.repositories.fulfillment_repository import FulfillmentRepository
    from fittrack.repositories.prize_repository import PrizeRepository
    from fittrack.repositories.ticket_repository import TicketRepository
    from fittrack.services.drawings import DrawingService
    from fittrack.services.drawing_executor import DrawingExecutor
    from fittrack.workers.drawing_worker import DrawingWorker

    try:
        pool = _get_pool()
    except Exception as exc:
        logger.error("Cannot connect to database: %s", exc)
        logger.info("Drawing worker: no DB — exiting gracefully")
        return 0

    drawing_repo = DrawingRepository(pool=pool)
    ticket_repo = TicketRepository(pool=pool)
    prize_repo = PrizeRepository(pool=pool)
    fulfillment_repo = FulfillmentRepository(pool=pool)

    drawing_svc = DrawingService(
        drawing_repo=drawing_repo,
        ticket_repo=ticket_repo,
        prize_repo=prize_repo,
    )
    executor = DrawingExecutor(
        drawing_repo=drawing_repo,
        ticket_repo=ticket_repo,
        prize_repo=prize_repo,
        fulfillment_repo=fulfillment_repo,
    )

    worker = DrawingWorker(
        drawing_service=drawing_svc,
        drawing_executor=executor,
    )
    result = worker.run()
    r = result.to_dict()
    logger.info(
        "Drawing complete: closed=%d executed=%d errors=%d",
        len(r.get("sales_closed", [])),
        len(r.get("drawings_executed", [])),
        len(r.get("errors", [])),
    )
    return 0


WORKERS = {
    "sync": run_sync,
    "leaderboard": run_leaderboard,
    "drawing": run_drawing,
}


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Run a FitTrack worker once",
        prog="python -m fittrack.workers.run",
    )
    parser.add_argument(
        "worker",
        choices=list(WORKERS.keys()),
        help="Which worker to run",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    args = parser.parse_args()
    setup_logging(level=args.log_level.upper())

    logger.info("Running worker: %s", args.worker)
    exit_code = WORKERS[args.worker]()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
