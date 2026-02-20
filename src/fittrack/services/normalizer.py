"""Activity normalizer — deduplication and normalization of raw activities."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fittrack.services.providers.base import RawActivity

logger = logging.getLogger(__name__)


class DuplicateActivityError(Exception):
    """Raised when an activity is a duplicate of an existing one."""

    def __init__(self, existing_id: str, reason: str) -> None:
        self.existing_id = existing_id
        self.reason = reason
        super().__init__(f"Duplicate of {existing_id}: {reason}")


class NormalizerError(Exception):
    """Error during activity normalization."""


def normalize_activity(
    raw: RawActivity,
    user_id: str,
    connection_id: str,
) -> dict[str, Any]:
    """Convert a RawActivity into a dict ready for DB insertion.

    The returned dict matches the ``activities`` table column layout.
    """
    data: dict[str, Any] = {
        "user_id": user_id,
        "connection_id": connection_id,
        "external_id": raw.external_id,
        "activity_type": raw.activity_type,
        "start_time": raw.start_time,
        "end_time": raw.end_time,
        "duration_minutes": raw.duration_minutes,
        "intensity": raw.intensity,
        "metrics": _serialize_metrics(raw.metrics),
        "points_earned": 0,  # calculated later by points service
        "processed": 0,  # not yet processed for points
    }
    return data


def _serialize_metrics(metrics: dict[str, Any]) -> str:
    """Serialize metrics dict to a JSON string for Oracle JSON column."""
    import json

    return json.dumps(metrics) if metrics else "{}"


def detect_duplicate(
    raw: RawActivity,
    user_id: str,
    existing_activities: list[dict[str, Any]],
) -> str | None:
    """Check if a RawActivity duplicates an existing stored activity.

    Duplicate detection rules:
    1. Same external_id from same provider → definite duplicate
    2. Same user + type + overlapping time window → probable duplicate

    Returns the activity_id of the duplicate, or None.
    """
    for existing in existing_activities:
        # Rule 1: same external_id
        if (
            existing.get("external_id") == raw.external_id
            and existing.get("user_id") == user_id
        ):
            return existing.get("activity_id", "unknown")

        # Rule 2: same type + overlapping time
        if (
            existing.get("activity_type") == raw.activity_type
            and existing.get("user_id") == user_id
            and _times_overlap(
                raw.start_time,
                raw.end_time,
                existing.get("start_time"),
                existing.get("end_time"),
            )
        ):
            return existing.get("activity_id", "unknown")

    return None


def _times_overlap(
    start1: datetime | None,
    end1: datetime | None,
    start2: Any,
    end2: Any,
) -> bool:
    """Check if two time ranges overlap.

    If either range has no end_time, treat them as point events
    that overlap only if start times are equal.
    """
    if start1 is None or start2 is None:
        return False

    # Parse strings if needed
    if isinstance(start2, str):
        start2 = datetime.fromisoformat(start2)
    if isinstance(end2, str):
        end2 = datetime.fromisoformat(end2)

    if end1 is None or end2 is None:
        return start1 == start2

    return start1 < end2 and start2 < end1


def resolve_multi_tracker_conflict(
    activities: list[dict[str, Any]],
    primary_provider: str | None = None,
) -> dict[str, Any]:
    """Given overlapping activities from multiple trackers, pick the best.

    Priority rules (from CLAUDE.md):
    1. Primary tracker (user-designated)
    2. Most detailed (most metrics keys)
    3. First received (earliest created_at)
    """
    if not activities:
        raise NormalizerError("No activities to resolve")

    if len(activities) == 1:
        return activities[0]

    # Sort by priority
    def sort_key(act: dict[str, Any]) -> tuple[int, int, str]:
        is_primary = 0 if act.get("provider") == primary_provider else 1
        metrics = act.get("metrics", {})
        metric_count = len(metrics) if isinstance(metrics, dict) else 0
        created = act.get("created_at", "9999")
        if not isinstance(created, str):
            created = str(created)
        return (is_primary, -metric_count, created)

    sorted_acts = sorted(activities, key=sort_key)
    return sorted_acts[0]
