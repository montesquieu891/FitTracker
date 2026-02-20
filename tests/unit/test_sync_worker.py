"""Tests for sync worker batch processing."""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.services.providers.base import ProviderError, RawActivity
from fittrack.workers.sync_worker import SYNC_INTERVAL_MINUTES, SyncResult, SyncWorker


def _make_connection(
    user_id: str = "user1",
    provider: str = "google_fit",
    connection_id: str = "conn1",
    last_sync_at: datetime | None = None,
    sync_status: str = "connected",
    access_token: str | None = None,
) -> dict[str, Any]:
    if access_token is None:
        access_token = base64.urlsafe_b64encode(b"stub_token").decode()
    return {
        "connection_id": connection_id,
        "user_id": user_id,
        "provider": provider,
        "access_token": access_token,
        "sync_status": sync_status,
        "last_sync_at": last_sync_at,
    }


def _make_raw_activity(
    activity_type: str = "steps",
    external_id: str = "ext1",
    provider: str = "google_fit",
) -> RawActivity:
    return RawActivity(
        external_id=external_id,
        provider=provider,
        activity_type=activity_type,
        start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        duration_minutes=60,
        metrics={"step_count": 8000},
    )


class MockRepo:
    """Simple in-memory mock for repositories."""

    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._items: list[dict[str, Any]] = items or []
        self._created: list[dict[str, Any]] = []
        self._updates: list[tuple[str, dict[str, Any]]] = []

    def find_all(self, limit: int = 100, offset: int = 0, **kw: Any) -> list[dict[str, Any]]:
        return self._items[offset : offset + limit]

    def find_by_user_id(self, user_id: str) -> list[dict[str, Any]]:
        return [i for i in self._items if i.get("user_id") == user_id]

    def find_by_user_and_date_range(
        self, user_id: str, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        return [i for i in self._items if i.get("user_id") == user_id]

    def create(self, data: dict[str, Any], new_id: str = "") -> dict[str, Any]:
        data["id"] = new_id
        self._created.append(data)
        self._items.append(data)
        return data

    def update(self, item_id: str, data: dict[str, Any]) -> dict[str, Any]:
        self._updates.append((item_id, data))
        return data

    def delete(self, item_id: str) -> bool:
        self._items = [i for i in self._items if i.get("id") != item_id]
        return True

    def count(self, **kw: Any) -> int:
        return len(self._items)


class MockProvider:
    """Mock provider for testing sync_connection."""

    def __init__(
        self,
        activities: list[RawActivity] | None = None,
        error: ProviderError | None = None,
    ) -> None:
        self._activities = activities or []
        self._error = error
        self.provider_name = "google_fit"

    def fetch_activities(
        self, access_token: str, start_time: datetime, end_time: datetime
    ) -> list[RawActivity]:
        if self._error:
            raise self._error
        return self._activities


class MockPointsService:
    """Mock points service for testing."""

    def __init__(self, points_per_activity: int = 10) -> None:
        self.points_per_activity = points_per_activity
        self.awards: list[tuple[str, dict[str, Any]]] = []

    def award_points_for_activity(
        self, user_id: str, activity: dict[str, Any]
    ) -> dict[str, Any]:
        self.awards.append((user_id, activity))
        return {"points_awarded": self.points_per_activity}


# ── SyncResult ──────────────────────────────────────────────────────


class TestSyncResult:
    def test_creation(self):
        r = SyncResult("user1", "google_fit")
        assert r.user_id == "user1"
        assert r.provider == "google_fit"
        assert r.activities_fetched == 0
        assert r.success is True

    def test_to_dict(self):
        r = SyncResult("u1", "fitbit")
        r.activities_fetched = 5
        r.activities_stored = 3
        r.duplicates_skipped = 2
        r.points_awarded = 150
        d = r.to_dict()
        assert d["activities_fetched"] == 5
        assert d["activities_stored"] == 3
        assert d["duplicates_skipped"] == 2
        assert d["points_awarded"] == 150
        assert d["success"] is True


# ── SyncWorker._get_due_connections ────────────────────────────────


class TestGetDueConnections:
    def test_never_synced_is_due(self):
        conn = _make_connection(last_sync_at=None)
        conn_repo = MockRepo([conn])
        worker = SyncWorker(conn_repo, MockRepo(), MockPointsService())
        due = worker._get_due_connections()
        assert len(due) == 1

    def test_recently_synced_not_due(self):
        conn = _make_connection(last_sync_at=datetime.now(tz=UTC) - timedelta(minutes=5))
        conn_repo = MockRepo([conn])
        worker = SyncWorker(conn_repo, MockRepo(), MockPointsService())
        due = worker._get_due_connections()
        assert len(due) == 0

    def test_old_sync_is_due(self):
        conn = _make_connection(
            last_sync_at=datetime.now(tz=UTC) - timedelta(minutes=SYNC_INTERVAL_MINUTES + 1)
        )
        conn_repo = MockRepo([conn])
        worker = SyncWorker(conn_repo, MockRepo(), MockPointsService())
        due = worker._get_due_connections()
        assert len(due) == 1

    def test_disconnected_excluded(self):
        conn = _make_connection(sync_status="disconnected", last_sync_at=None)
        conn_repo = MockRepo([conn])
        worker = SyncWorker(conn_repo, MockRepo(), MockPointsService())
        due = worker._get_due_connections()
        assert len(due) == 0

    def test_string_last_sync_at(self):
        old_time = (datetime.now(tz=UTC) - timedelta(hours=1)).isoformat()
        conn = _make_connection(last_sync_at=old_time)
        conn_repo = MockRepo([conn])
        worker = SyncWorker(conn_repo, MockRepo(), MockPointsService())
        due = worker._get_due_connections()
        assert len(due) == 1


# ── SyncWorker.sync_connection ─────────────────────────────────────


class TestSyncConnection:
    def test_no_provider_returns_failure(self):
        conn = _make_connection()
        worker = SyncWorker(MockRepo(), MockRepo(), MockPointsService(), providers={})
        result = worker.sync_connection(conn)
        assert result.success is False
        assert "No provider client" in result.errors[0]

    def test_no_access_token_returns_failure(self):
        conn = _make_connection(access_token="")
        provider = MockProvider()
        worker = SyncWorker(
            MockRepo(), MockRepo(), MockPointsService(),
            providers={"google_fit": provider},
        )
        result = worker.sync_connection(conn)
        assert result.success is False
        assert "No access token" in result.errors[0]

    def test_provider_fetch_error(self):
        conn = _make_connection()
        provider = MockProvider(error=ProviderError("google_fit", "API down"))
        worker = SyncWorker(
            MockRepo([conn]), MockRepo(), MockPointsService(),
            providers={"google_fit": provider},
        )
        result = worker.sync_connection(conn)
        assert result.success is False
        assert "Fetch failed" in result.errors[0]

    def test_successful_sync_with_activities(self):
        conn = _make_connection()
        raw = _make_raw_activity()
        provider = MockProvider(activities=[raw])
        activity_repo = MockRepo()
        points = MockPointsService(points_per_activity=50)
        conn_repo = MockRepo([conn])
        worker = SyncWorker(
            conn_repo, activity_repo, points,
            providers={"google_fit": provider},
        )
        result = worker.sync_connection(conn)
        assert result.success is True
        assert result.activities_fetched == 1
        assert result.activities_stored == 1
        assert result.points_awarded == 50

    def test_duplicate_activity_skipped(self):
        """Activities that already exist are skipped (dedup by external_id)."""
        conn = _make_connection()
        raw = _make_raw_activity(external_id="ext_dup")
        provider = MockProvider(activities=[raw])
        # Existing activity with same external_id
        existing = {
            "activity_id": "existing1",
            "user_id": "user1",
            "external_id": "ext_dup",
            "activity_type": "steps",
            "provider": "google_fit",
        }
        activity_repo = MockRepo([existing])
        worker = SyncWorker(
            MockRepo([conn]), activity_repo, MockPointsService(),
            providers={"google_fit": provider},
        )
        result = worker.sync_connection(conn)
        assert result.duplicates_skipped == 1
        assert result.activities_stored == 0

    def test_connection_updated_after_sync(self):
        conn = _make_connection()
        conn_repo = MockRepo([conn])
        provider = MockProvider(activities=[])
        worker = SyncWorker(
            conn_repo, MockRepo(), MockPointsService(),
            providers={"google_fit": provider},
        )
        worker.sync_connection(conn)
        # Check last update was sync status
        assert len(conn_repo._updates) > 0
        last_update = conn_repo._updates[-1]
        assert last_update[1].get("sync_status") == "synced"


# ── SyncWorker.run_batch ───────────────────────────────────────────


class TestRunBatch:
    def test_empty_batch(self):
        worker = SyncWorker(MockRepo(), MockRepo(), MockPointsService())
        results = worker.run_batch()
        assert results == []

    def test_batch_processes_due_connections(self):
        conn = _make_connection(last_sync_at=None)
        provider = MockProvider(activities=[_make_raw_activity()])
        worker = SyncWorker(
            MockRepo([conn]), MockRepo(), MockPointsService(points_per_activity=25),
            providers={"google_fit": provider},
        )
        results = worker.run_batch()
        assert len(results) == 1
        assert results[0]["success"] is True
        assert results[0]["activities_stored"] == 1

    def test_batch_isolates_failures(self):
        """One connection failing doesn't block others."""
        conn1 = _make_connection(user_id="u1", connection_id="c1")
        conn2 = _make_connection(user_id="u2", connection_id="c2")
        # Provider that fails
        provider = MockProvider(error=ProviderError("google_fit", "API down"))
        conn_repo = MockRepo([conn1, conn2])
        worker = SyncWorker(
            conn_repo, MockRepo(), MockPointsService(),
            providers={"google_fit": provider},
        )
        results = worker.run_batch()
        assert len(results) == 2
        # Both fail because error provider, but they're isolated
        for r in results:
            assert r["success"] is False

    def test_batch_multiple_providers(self):
        gf_conn = _make_connection(provider="google_fit", connection_id="c1")
        fb_conn = _make_connection(provider="fitbit", connection_id="c2")

        gf_raw = _make_raw_activity(provider="google_fit", external_id="gf1")
        fb_raw = _make_raw_activity(provider="fitbit", external_id="fb1")

        gf_provider = MockProvider(activities=[gf_raw])
        gf_provider.provider_name = "google_fit"
        fb_provider = MockProvider(activities=[fb_raw])
        fb_provider.provider_name = "fitbit"

        worker = SyncWorker(
            MockRepo([gf_conn, fb_conn]),
            MockRepo(),
            MockPointsService(),
            providers={"google_fit": gf_provider, "fitbit": fb_provider},
        )
        results = worker.run_batch()
        assert len(results) == 2
        assert all(r["success"] for r in results)
