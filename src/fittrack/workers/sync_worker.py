"""Sync worker — batch synchronization of fitness data from providers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.services.normalizer import detect_duplicate, normalize_activity
from fittrack.services.providers.base import BaseProvider, ProviderError
from fittrack.services.trackers import _decrypt_token

logger = logging.getLogger(__name__)

# Re-exported for external callers
SYNC_INTERVAL_MINUTES = 15


class SyncError(Exception):
    """Error during sync process."""

    def __init__(self, user_id: str, provider: str, detail: str) -> None:
        self.user_id = user_id
        self.provider = provider
        self.detail = detail
        super().__init__(f"Sync error for {user_id}/{provider}: {detail}")


class SyncResult:
    """Result of syncing a single user/connection."""

    def __init__(self, user_id: str, provider: str) -> None:
        self.user_id = user_id
        self.provider = provider
        self.activities_fetched: int = 0
        self.activities_stored: int = 0
        self.duplicates_skipped: int = 0
        self.points_awarded: int = 0
        self.errors: list[str] = []
        self.success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "provider": self.provider,
            "activities_fetched": self.activities_fetched,
            "activities_stored": self.activities_stored,
            "duplicates_skipped": self.duplicates_skipped,
            "points_awarded": self.points_awarded,
            "errors": self.errors,
            "success": self.success,
        }


class SyncWorker:
    """Batch sync worker that processes all pending connections.

    Designed to be run on a schedule (every 15 minutes).
    Processes each user independently — one failure doesn't block others.
    """

    def __init__(
        self,
        connection_repo: Any,
        activity_repo: Any,
        points_service: Any,
        providers: dict[str, BaseProvider] | None = None,
    ) -> None:
        self.connection_repo = connection_repo
        self.activity_repo = activity_repo
        self.points_service = points_service
        self.providers = providers or {}

    def run_batch(self) -> list[dict[str, Any]]:
        """Process all connections due for sync.

        Returns a list of SyncResult dicts.
        """
        due_connections = self._get_due_connections()
        logger.info("Sync batch: %d connections due", len(due_connections))

        results: list[dict[str, Any]] = []
        for conn in due_connections:
            try:
                result = self.sync_connection(conn)
                results.append(result.to_dict())
            except Exception as e:
                user_id = conn.get("user_id", "unknown")
                provider = conn.get("provider", "unknown")
                logger.error("Sync failed for %s/%s: %s", user_id, provider, e, exc_info=True)
                error_result = SyncResult(user_id, provider)
                error_result.success = False
                error_result.errors.append(str(e))
                results.append(error_result.to_dict())

                # Update connection with error status
                conn_id = conn.get("connection_id", "")
                if conn_id:
                    import contextlib

                    with contextlib.suppress(Exception):
                        self.connection_repo.update(
                            conn_id,
                            {
                                "sync_status": "error",
                                "error_message": str(e)[:500],
                                "updated_at": datetime.now(tz=UTC),
                            },
                        )

        logger.info(
            "Sync batch complete: %d processed, %d success",
            len(results),
            sum(1 for r in results if r.get("success")),
        )
        return results

    def sync_connection(self, connection: dict[str, Any]) -> SyncResult:
        """Sync a single connection — fetch, normalize, deduplicate, store, award points."""
        user_id = connection.get("user_id", "")
        provider_name = connection.get("provider", "")
        connection_id = connection.get("connection_id", "")

        result = SyncResult(user_id, provider_name)

        # Get provider client
        provider = self.providers.get(provider_name)
        if not provider:
            result.success = False
            result.errors.append(f"No provider client for {provider_name}")
            return result

        # Determine time range (last sync → now)
        last_sync = connection.get("last_sync_at")
        if last_sync is None:
            start_time = datetime.now(tz=UTC) - timedelta(days=1)
        elif isinstance(last_sync, str):
            start_time = datetime.fromisoformat(last_sync)
        else:
            start_time = last_sync
        end_time = datetime.now(tz=UTC)

        # Ensure timezone-aware
        if hasattr(start_time, "tzinfo") and start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=UTC)

        # Get access token
        access_token_enc = connection.get("access_token", "")
        if not access_token_enc:
            result.success = False
            result.errors.append("No access token")
            return result

        access_token = _decrypt_token(access_token_enc)

        # Fetch activities
        try:
            raw_activities = provider.fetch_activities(access_token, start_time, end_time)
            result.activities_fetched = len(raw_activities)
        except ProviderError as e:
            result.success = False
            result.errors.append(f"Fetch failed: {e.detail}")
            return result

        # Get existing activities for deduplication
        try:
            existing = self.activity_repo.find_by_user_and_date_range(user_id, start_time, end_time)
        except Exception:
            existing = []

        # Process each activity
        for raw in raw_activities:
            try:
                # Deduplicate
                dup_id = detect_duplicate(raw, user_id, existing)
                if dup_id:
                    result.duplicates_skipped += 1
                    continue

                # Normalize
                activity_data = normalize_activity(raw, user_id, connection_id)

                # Store
                import uuid

                activity_id = uuid.uuid4().hex
                self.activity_repo.create(data=activity_data, new_id=activity_id)
                activity_data["activity_id"] = activity_id
                result.activities_stored += 1

                # Award points
                try:
                    points_result = self.points_service.award_points_for_activity(
                        user_id, activity_data
                    )
                    awarded = points_result.get("points_awarded", 0)
                    result.points_awarded += awarded

                    # Update the activity with points earned
                    if awarded > 0:
                        self.activity_repo.update(
                            activity_id,
                            {
                                "points_earned": awarded,
                                "processed": 1,
                            },
                        )
                except Exception as e:
                    result.errors.append(f"Points error: {e}")

                # Add to existing list for subsequent dedup checks
                existing.append(activity_data)

            except Exception as e:
                result.errors.append(f"Activity processing error: {e}")

        # Update connection with last sync time
        try:
            self.connection_repo.update(
                connection_id,
                {
                    "last_sync_at": end_time,
                    "sync_status": "synced" if result.success else "error",
                    "error_message": ("; ".join(result.errors[:3]) if result.errors else None),
                    "updated_at": datetime.now(tz=UTC),
                },
            )
        except Exception as e:
            result.errors.append(f"Connection update error: {e}")

        return result

    def _get_due_connections(self) -> list[dict[str, Any]]:
        """Get all connections due for sync.

        A connection is due if:
        - sync_status is not 'error' (permanently failed)
        - last_sync_at is None or older than SYNC_INTERVAL_MINUTES
        """
        all_connections = self.connection_repo.find_all(limit=1000, offset=0)
        cutoff = datetime.now(tz=UTC) - timedelta(minutes=SYNC_INTERVAL_MINUTES)

        due: list[dict[str, Any]] = []
        for conn in all_connections:
            status = conn.get("sync_status", "")
            if status == "disconnected":
                continue

            last_sync = conn.get("last_sync_at")
            if last_sync is None:
                due.append(conn)
                continue

            if isinstance(last_sync, str):
                try:
                    last_sync = datetime.fromisoformat(last_sync)
                except ValueError:
                    due.append(conn)
                    continue

            if hasattr(last_sync, "tzinfo") and last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=UTC)

            if last_sync < cutoff:
                due.append(conn)

        return due
