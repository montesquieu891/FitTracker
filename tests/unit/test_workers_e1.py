"""Checkpoint E — Worker integration tests.

Tests verify that each worker can be instantiated and run once
without crashing, using mock repos that simulate the seeded DB.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

# ── Fake repos ──────────────────────────────────────────────────────


class FakeRepo:
    """Minimal fake repository for worker tests."""

    def __init__(self, rows: list[dict[str, Any]] | None = None) -> None:
        self._rows = rows or []

    def find_all(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        return self._rows[offset : offset + limit]

    def find_by_id(self, uid: str) -> dict[str, Any] | None:
        return next((r for r in self._rows if r.get(self._id_col(), "") == uid), None)

    def find_by_field(self, field: str, value: Any) -> list[dict[str, Any]]:
        return [r for r in self._rows if r.get(field) == value]

    def find_by_tier_code(self, code: str) -> list[dict[str, Any]]:
        return [r for r in self._rows if r.get("tier_code") == code]

    def find_by_user_and_date_range(
        self, user_id: str, start: Any, end: Any
    ) -> list[dict[str, Any]]:
        return [r for r in self._rows if r.get("user_id") == user_id]

    def create(self, *, data: dict[str, Any], new_id: str) -> str:
        self._rows.append({**data, self._id_col(): new_id})
        return new_id

    def update(self, uid: str, data: dict[str, Any]) -> int:
        for r in self._rows:
            if r.get(self._id_col()) == uid:
                r.update(data)
                return 1
        return 0

    def _id_col(self) -> str:
        return "id"


# ── E1: Sync worker ────────────────────────────────────────────────


class TestE1SyncWorker:
    """Sync worker runs without crashing if no real providers configured."""

    def test_sync_no_connections(self) -> None:
        """With zero connections, run_batch returns empty list."""
        from fittrack.workers.sync_worker import SyncWorker

        worker = SyncWorker(
            connection_repo=FakeRepo([]),
            activity_repo=FakeRepo(),
            points_service=MagicMock(),
            providers={},
        )
        results = worker.run_batch()
        assert results == []

    def test_sync_connections_no_provider(self) -> None:
        """Connections exist but no matching provider → graceful failure per connection."""
        from fittrack.workers.sync_worker import SyncWorker

        conns = [
            {
                "connection_id": "c1",
                "user_id": "u1",
                "provider": "google_fit",
                "sync_status": "pending",
                "last_sync_at": None,
                "access_token": "fake_encrypted_token",
            },
        ]
        worker = SyncWorker(
            connection_repo=FakeRepo(conns),
            activity_repo=FakeRepo(),
            points_service=MagicMock(),
            providers={},  # no real providers
        )
        results = worker.run_batch()
        assert len(results) == 1
        assert results[0]["success"] is False
        assert any("No provider" in e for e in results[0]["errors"])

    def test_sync_returns_result_format(self) -> None:
        """SyncResult.to_dict has expected keys."""
        from fittrack.workers.sync_worker import SyncResult

        r = SyncResult("u1", "google_fit")
        d = r.to_dict()
        assert "user_id" in d
        assert "provider" in d
        assert "activities_fetched" in d
        assert "success" in d


# ── E1: Leaderboard worker ─────────────────────────────────────────


class TestE1LeaderboardWorker:
    """Leaderboard worker runs without crashing."""

    def test_leaderboard_no_tiers(self) -> None:
        """No active tiers → still completes."""
        from fittrack.services.leaderboard import LeaderboardService
        from fittrack.workers.leaderboard_worker import LeaderboardWorker

        lb_svc = LeaderboardService(
            transaction_repo=FakeRepo(),
            profile_repo=FakeRepo(),
            activity_repo=FakeRepo(),
            cache_service=None,
        )
        worker = LeaderboardWorker(
            leaderboard_service=lb_svc,
            profile_repo=FakeRepo(),
            cache_service=None,
        )
        result = worker.run()
        assert result["success"] is True
        # At least global tier processed (tier_code=None)
        assert result["tiers_processed"] >= 1

    def test_leaderboard_result_format(self) -> None:
        """LeaderboardWorkerResult.to_dict has expected keys."""
        from fittrack.workers.leaderboard_worker import LeaderboardWorkerResult

        r = LeaderboardWorkerResult()
        d = r.to_dict()
        assert "tiers_processed" in d
        assert "periods_processed" in d
        assert "entries_cached" in d
        assert "success" in d


# ── E1: Drawing worker ─────────────────────────────────────────────


class TestE1DrawingWorker:
    """Drawing worker runs without crashing when no drawings are due."""

    def test_drawing_no_open_or_closed(self) -> None:
        """No open/closed drawings → worker does nothing."""
        from fittrack.workers.drawing_worker import DrawingWorker

        drawing_svc = MagicMock()
        drawing_svc.drawing_repo = FakeRepo([])  # no drawings
        executor = MagicMock()

        worker = DrawingWorker(drawing_service=drawing_svc, drawing_executor=executor)
        result = worker.run()
        d = result.to_dict()
        assert d["success"] is True
        assert d["sales_closed"] == []
        assert d["drawings_executed"] == []

    def test_drawing_open_but_not_due(self) -> None:
        """Open drawings exist but drawing_time is far in the future."""
        from fittrack.workers.drawing_worker import DrawingWorker

        future = datetime.now(tz=UTC) + timedelta(days=30)
        drawings = [
            {"drawing_id": "d1", "status": "open", "drawing_time": future.isoformat()},
        ]
        drawing_svc = MagicMock()
        drawing_svc.drawing_repo = FakeRepo(drawings)
        drawing_svc.check_sales_should_close.return_value = False
        executor = MagicMock()

        worker = DrawingWorker(drawing_service=drawing_svc, drawing_executor=executor)
        result = worker.run()
        d = result.to_dict()
        assert d["sales_closed"] == []

    def test_drawing_result_format(self) -> None:
        """DrawingWorkerResult.to_dict has expected keys."""
        from fittrack.workers.drawing_worker import DrawingWorkerResult

        r = DrawingWorkerResult()
        d = r.to_dict()
        assert "sales_closed" in d
        assert "drawings_executed" in d
        assert "errors" in d
        assert "success" in d


# ── E1: Worker CLI runner structure ─────────────────────────────────


class TestE1WorkerCLI:
    """Worker CLI entry point is importable and has correct structure."""

    def test_workers_dict_has_all_three(self) -> None:
        from fittrack.workers.run import WORKERS

        assert "sync" in WORKERS
        assert "leaderboard" in WORKERS
        assert "drawing" in WORKERS

    def test_main_callable(self) -> None:
        from fittrack.workers.run import main

        assert callable(main)
