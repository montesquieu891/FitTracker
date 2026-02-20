"""Tests for the activity normalizer — normalization and deduplication."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fittrack.services.normalizer import (
    NormalizerError,
    detect_duplicate,
    normalize_activity,
    resolve_multi_tracker_conflict,
)
from fittrack.services.providers.base import RawActivity

# ── Normalization ───────────────────────────────────────────────────


class TestNormalizeActivity:
    def _make_raw(self, **kwargs):
        defaults = {
            "external_id": "ext_001",
            "provider": "google_fit",
            "activity_type": "steps",
            "start_time": datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            "end_time": datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
            "metrics": {"step_count": 10000},
        }
        defaults.update(kwargs)
        return RawActivity(**defaults)

    def test_basic_normalization(self):
        raw = self._make_raw()
        result = normalize_activity(raw, "user1", "conn1")
        assert result["user_id"] == "user1"
        assert result["connection_id"] == "conn1"
        assert result["external_id"] == "ext_001"
        assert result["activity_type"] == "steps"
        assert result["points_earned"] == 0
        assert result["processed"] == 0

    def test_workout_normalization(self):
        raw = self._make_raw(
            activity_type="workout",
            duration_minutes=30,
            intensity="moderate",
            metrics={"calories_burned": 240},
        )
        result = normalize_activity(raw, "user1", "conn1")
        assert result["activity_type"] == "workout"
        assert result["duration_minutes"] == 30
        assert result["intensity"] == "moderate"

    def test_metrics_serialized_as_json(self):
        raw = self._make_raw(metrics={"step_count": 5000, "distance_km": 3.5})
        result = normalize_activity(raw, "user1", "conn1")
        import json
        parsed = json.loads(result["metrics"])
        assert parsed["step_count"] == 5000
        assert parsed["distance_km"] == 3.5

    def test_empty_metrics(self):
        raw = self._make_raw(metrics={})
        result = normalize_activity(raw, "user1", "conn1")
        assert result["metrics"] == "{}"


# ── Duplicate Detection ────────────────────────────────────────────


class TestDetectDuplicate:
    def test_no_existing_no_duplicate(self):
        raw = RawActivity(
            external_id="ext_001",
            provider="google_fit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        )
        assert detect_duplicate(raw, "user1", []) is None

    def test_same_external_id_is_duplicate(self):
        raw = RawActivity(
            external_id="ext_001",
            provider="google_fit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        )
        existing = [
            {"activity_id": "act1", "external_id": "ext_001", "user_id": "user1"}
        ]
        assert detect_duplicate(raw, "user1", existing) == "act1"

    def test_different_external_id_not_duplicate(self):
        raw = RawActivity(
            external_id="ext_002",
            provider="google_fit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        )
        existing = [
            {"activity_id": "act1", "external_id": "ext_001", "user_id": "user1"}
        ]
        assert detect_duplicate(raw, "user1", existing) is None

    def test_same_type_overlapping_time_is_duplicate(self):
        raw = RawActivity(
            external_id="ext_new",
            provider="fitbit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
        )
        existing = [
            {
                "activity_id": "act1",
                "external_id": "ext_old",
                "user_id": "user1",
                "activity_type": "steps",
                "start_time": datetime(2026, 1, 15, 0, 0, tzinfo=UTC),
                "end_time": datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
            }
        ]
        assert detect_duplicate(raw, "user1", existing) == "act1"

    def test_same_type_non_overlapping(self):
        raw = RawActivity(
            external_id="ext_new",
            provider="fitbit",
            activity_type="steps",
            start_time=datetime(2026, 1, 16, 0, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 16, 23, 59, tzinfo=UTC),
        )
        existing = [
            {
                "activity_id": "act1",
                "external_id": "ext_old",
                "user_id": "user1",
                "activity_type": "steps",
                "start_time": datetime(2026, 1, 15, 0, 0, tzinfo=UTC),
                "end_time": datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
            }
        ]
        assert detect_duplicate(raw, "user1", existing) is None

    def test_different_user_not_duplicate(self):
        raw = RawActivity(
            external_id="ext_001",
            provider="google_fit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        )
        existing = [
            {"activity_id": "act1", "external_id": "ext_001", "user_id": "user2"}
        ]
        assert detect_duplicate(raw, "user1", existing) is None

    def test_different_type_not_duplicate(self):
        raw = RawActivity(
            external_id="ext_new",
            provider="fitbit",
            activity_type="workout",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 15, 9, 0, tzinfo=UTC),
        )
        existing = [
            {
                "activity_id": "act1",
                "external_id": "ext_old",
                "user_id": "user1",
                "activity_type": "steps",
                "start_time": datetime(2026, 1, 15, 0, 0, tzinfo=UTC),
                "end_time": datetime(2026, 1, 15, 23, 59, tzinfo=UTC),
            }
        ]
        assert detect_duplicate(raw, "user1", existing) is None

    def test_no_end_time_same_start_is_duplicate(self):
        raw = RawActivity(
            external_id="ext_new",
            provider="fitbit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
        )
        existing = [
            {
                "activity_id": "act1",
                "external_id": "ext_old",
                "user_id": "user1",
                "activity_type": "steps",
                "start_time": datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            }
        ]
        assert detect_duplicate(raw, "user1", existing) == "act1"

    def test_string_timestamps_handled(self):
        raw = RawActivity(
            external_id="ext_new",
            provider="fitbit",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            end_time=datetime(2026, 1, 15, 23, 0, tzinfo=UTC),
        )
        existing = [
            {
                "activity_id": "act1",
                "external_id": "ext_old",
                "user_id": "user1",
                "activity_type": "steps",
                "start_time": "2026-01-15T00:00:00+00:00",
                "end_time": "2026-01-15T23:59:00+00:00",
            }
        ]
        assert detect_duplicate(raw, "user1", existing) == "act1"


# ── Multi-Tracker Conflict Resolution ──────────────────────────────


class TestResolveMultiTrackerConflict:
    def test_single_activity(self):
        activities = [{"activity_id": "a1", "provider": "google_fit"}]
        result = resolve_multi_tracker_conflict(activities)
        assert result["activity_id"] == "a1"

    def test_empty_list_raises(self):
        with pytest.raises(NormalizerError, match="No activities"):
            resolve_multi_tracker_conflict([])

    def test_primary_tracker_wins(self):
        activities = [
            {
                "activity_id": "a1",
                "provider": "fitbit",
                "metrics": {"step_count": 10000},
                "created_at": "2026-01-15T00:00:00",
            },
            {
                "activity_id": "a2",
                "provider": "google_fit",
                "metrics": {"step_count": 9000},
                "created_at": "2026-01-15T01:00:00",
            },
        ]
        result = resolve_multi_tracker_conflict(
            activities, primary_provider="google_fit"
        )
        assert result["activity_id"] == "a2"

    def test_most_detailed_wins_without_primary(self):
        activities = [
            {
                "activity_id": "a1",
                "provider": "fitbit",
                "metrics": {"step_count": 10000},
                "created_at": "2026-01-15T01:00:00",
            },
            {
                "activity_id": "a2",
                "provider": "google_fit",
                "metrics": {"step_count": 10000, "distance_km": 5.2, "speed": 4.5},
                "created_at": "2026-01-15T01:00:00",
            },
        ]
        result = resolve_multi_tracker_conflict(activities)
        assert result["activity_id"] == "a2"

    def test_first_received_breaks_tie(self):
        activities = [
            {
                "activity_id": "a1",
                "provider": "fitbit",
                "metrics": {"step_count": 10000},
                "created_at": "2026-01-15T01:00:00",
            },
            {
                "activity_id": "a2",
                "provider": "google_fit",
                "metrics": {"step_count": 10000},
                "created_at": "2026-01-15T00:00:00",
            },
        ]
        result = resolve_multi_tracker_conflict(activities)
        assert result["activity_id"] == "a2"  # Earlier created_at
