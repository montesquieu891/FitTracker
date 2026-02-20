"""Tests for the anti-gaming service — cap enforcement and anomaly detection."""

from __future__ import annotations

from datetime import UTC, datetime

from fittrack.services.anti_gaming import (
    AntiGamingService,
    compute_tier_stats,
)


class MockRepo:
    """Minimal mock repo."""

    def __init__(self, data=None):
        self.data = data or []

    def find_by_user_id(self, user_id):
        return [d for d in self.data if d.get("user_id") == user_id]

    def find_by_user_and_date_range(self, user_id, start, end):
        return [d for d in self.data if d.get("user_id") == user_id]

    def find_by_id(self, entity_id):
        for item in self.data:
            if item.get("user_id") == entity_id:
                return item
        return None


def _make_service(txn_data=None, activity_data=None, user_data=None):
    return AntiGamingService(
        activity_repo=MockRepo(activity_data or []),
        user_repo=MockRepo(user_data or []),
        transaction_repo=MockRepo(txn_data or []),
    )


# ── Daily Cap ───────────────────────────────────────────────────────


class TestDailyCap:
    def test_no_prior_earnings(self):
        service = _make_service()
        result = service.check_daily_cap("u1", 500)
        assert result["allowed"] is True
        assert result["allowed_points"] == 500
        assert result["remaining"] == 1000

    def test_partial_earnings(self):
        now = datetime.now(tz=UTC)
        txns = [
            {
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 700,
                "created_at": now,
            }
        ]
        service = _make_service(txn_data=txns)
        result = service.check_daily_cap("u1", 500)
        assert result["allowed"] is True
        assert result["allowed_points"] == 300

    def test_at_cap(self):
        now = datetime.now(tz=UTC)
        txns = [
            {
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 1000,
                "created_at": now,
            }
        ]
        service = _make_service(txn_data=txns)
        result = service.check_daily_cap("u1", 500)
        assert result["allowed"] is False
        assert result["allowed_points"] == 0

    def test_over_cap(self):
        now = datetime.now(tz=UTC)
        txns = [
            {
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 1200,
                "created_at": now,
            }
        ]
        service = _make_service(txn_data=txns)
        result = service.check_daily_cap("u1", 100)
        assert result["allowed"] is False


# ── Workout Cap ─────────────────────────────────────────────────────


class TestWorkoutCap:
    def test_no_workouts(self):
        service = _make_service()
        result = service.check_workout_cap("u1")
        assert result["allowed"] is True
        assert result["remaining"] == 3

    def test_two_workouts(self):
        activities = [
            {
                "user_id": "u1",
                "activity_type": "workout",
                "duration_minutes": 30,
                "points_earned": 50,
            },
            {
                "user_id": "u1",
                "activity_type": "workout",
                "duration_minutes": 25,
                "points_earned": 50,
            },
        ]
        service = _make_service(activity_data=activities)
        result = service.check_workout_cap("u1")
        assert result["allowed"] is True
        assert result["remaining"] == 1

    def test_three_workouts_capped(self):
        activities = [
            {
                "user_id": "u1",
                "activity_type": "workout",
                "duration_minutes": 30,
                "points_earned": 50,
            }
            for _ in range(3)
        ]
        service = _make_service(activity_data=activities)
        result = service.check_workout_cap("u1")
        assert result["allowed"] is False
        assert result["remaining"] == 0


# ── Anomaly Detection ───────────────────────────────────────────────


class TestAnomalyDetection:
    def test_no_tier_stats(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 50000}}
        result = service.detect_anomaly("u1", activity, tier_stats=None)
        assert result["is_anomaly"] is False

    def test_within_normal_range(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 10000}}
        stats = {"avg": 8000, "stddev": 3000}
        result = service.detect_anomaly("u1", activity, tier_stats=stats)
        assert result["is_anomaly"] is False

    def test_anomalous_activity(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 50000}}
        stats = {"avg": 8000, "stddev": 3000}
        result = service.detect_anomaly("u1", activity, tier_stats=stats)
        assert result["is_anomaly"] is True
        assert result["z_score"] > 3.0

    def test_zero_stddev(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 10000}}
        stats = {"avg": 8000, "stddev": 0}
        result = service.detect_anomaly("u1", activity, tier_stats=stats)
        assert result["is_anomaly"] is False

    def test_workout_anomaly(self):
        service = _make_service()
        activity = {
            "activity_type": "workout",
            "duration_minutes": 300,
        }
        stats = {"avg": 30, "stddev": 15}
        result = service.detect_anomaly("u1", activity, tier_stats=stats)
        assert result["is_anomaly"] is True

    def test_borderline_not_anomaly(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 16000}}
        # z = (16000 - 8000) / 3000 ≈ 2.67, under 3.0
        stats = {"avg": 8000, "stddev": 3000}
        result = service.detect_anomaly("u1", activity, tier_stats=stats)
        assert result["is_anomaly"] is False


# ── Device Sharing ──────────────────────────────────────────────────


class TestDeviceSharing:
    def test_no_device_data(self):
        service = _make_service()
        result = service.check_device_sharing("dev1", "u1", known_devices=None)
        assert result["suspicious"] is False

    def test_no_sharing(self):
        service = _make_service()
        devices = [{"user_id": "u1", "device_id": "dev1"}]
        result = service.check_device_sharing("dev1", "u1", known_devices=devices)
        assert result["suspicious"] is False

    def test_sharing_detected(self):
        service = _make_service()
        devices = [
            {"user_id": "u1", "device_id": "dev1"},
            {"user_id": "u2", "device_id": "dev1"},
        ]
        result = service.check_device_sharing("dev1", "u1", known_devices=devices)
        assert result["suspicious"] is True
        assert result["other_user_count"] == 1

    def test_multiple_sharers(self):
        service = _make_service()
        devices = [
            {"user_id": "u1", "device_id": "dev1"},
            {"user_id": "u2", "device_id": "dev1"},
            {"user_id": "u3", "device_id": "dev1"},
        ]
        result = service.check_device_sharing("dev1", "u1", known_devices=devices)
        assert result["suspicious"] is True
        assert result["other_user_count"] == 2

    def test_empty_device_id(self):
        service = _make_service()
        result = service.check_device_sharing("", "u1", known_devices=[])
        assert result["suspicious"] is False


# ── Flag for Review ─────────────────────────────────────────────────


class TestFlagForReview:
    def test_basic_flag(self):
        service = _make_service()
        result = service.flag_for_review("u1", "anomaly", {"value": 50000})
        assert result["user_id"] == "u1"
        assert result["status"] == "pending_review"
        assert result["reason"] == "anomaly"


# ── Run All Checks ──────────────────────────────────────────────────


class TestRunAllChecks:
    def test_all_clear(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 5000}}
        result = service.run_all_checks("u1", activity, 50)
        assert result["allowed"] is True
        assert result["allowed_points"] == 50
        assert result["flags"] == []

    def test_daily_cap_blocks(self):
        now = datetime.now(tz=UTC)
        txns = [
            {
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 1000,
                "created_at": now,
            }
        ]
        service = _make_service(txn_data=txns)
        activity = {"activity_type": "steps", "metrics": {"step_count": 5000}}
        result = service.run_all_checks("u1", activity, 50)
        assert result["allowed"] is False
        assert "daily_cap_reached" in result["flags"]

    def test_workout_cap_blocks(self):
        activities = [
            {
                "user_id": "u1",
                "activity_type": "workout",
                "duration_minutes": 30,
                "points_earned": 50,
            }
            for _ in range(3)
        ]
        service = _make_service(activity_data=activities)
        activity = {"activity_type": "workout", "duration_minutes": 30}
        result = service.run_all_checks("u1", activity, 50)
        assert result["allowed"] is False
        assert "workout_cap_reached" in result["flags"]

    def test_anomaly_flags_but_allows(self):
        service = _make_service()
        activity = {"activity_type": "steps", "metrics": {"step_count": 50000}}
        stats = {"avg": 8000, "stddev": 3000}
        result = service.run_all_checks("u1", activity, 200, tier_stats=stats)
        # Anomalies don't block, just flag
        assert result["allowed"] is True
        assert any("anomaly" in f for f in result["flags"])


# ── Compute Tier Stats ──────────────────────────────────────────────


class TestComputeTierStats:
    def test_empty_activities(self):
        stats = compute_tier_stats([], "steps")
        assert stats["avg"] == 0
        assert stats["stddev"] == 0
        assert stats["count"] == 0

    def test_single_activity(self):
        activities = [
            {"activity_type": "steps", "metrics": {"step_count": 10000}}
        ]
        stats = compute_tier_stats(activities, "steps")
        assert stats["avg"] == 10000
        assert stats["stddev"] == 0
        assert stats["count"] == 1

    def test_multiple_activities(self):
        activities = [
            {"activity_type": "steps", "metrics": {"step_count": 8000}},
            {"activity_type": "steps", "metrics": {"step_count": 12000}},
        ]
        stats = compute_tier_stats(activities, "steps")
        assert stats["avg"] == 10000
        assert stats["count"] == 2
        assert stats["stddev"] == 2000

    def test_filters_by_type(self):
        activities = [
            {"activity_type": "steps", "metrics": {"step_count": 10000}},
            {"activity_type": "workout", "duration_minutes": 30},
        ]
        stats = compute_tier_stats(activities, "steps")
        assert stats["count"] == 1

    def test_workout_stats(self):
        activities = [
            {"activity_type": "workout", "duration_minutes": 30},
            {"activity_type": "workout", "duration_minutes": 60},
        ]
        stats = compute_tier_stats(activities, "workout")
        assert stats["avg"] == 45
        assert stats["count"] == 2
