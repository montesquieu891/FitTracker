"""Tests for points calculation engine — all rate table calculations."""

from __future__ import annotations

import pytest

from fittrack.services.points import (
    PointsError,
    PointsService,
    apply_daily_cap,
    calculate_active_minute_points,
    calculate_activity_points,
    calculate_step_goal_bonus,
    calculate_step_points,
    calculate_weekly_streak_bonus,
    calculate_workout_bonus,
)

# ── Step Points ─────────────────────────────────────────────────────


class TestCalculateStepPoints:
    def test_zero_steps(self):
        assert calculate_step_points(0) == 0

    def test_negative_steps(self):
        assert calculate_step_points(-500) == 0

    def test_500_steps(self):
        # 500 // 1000 = 0 → 0 points
        assert calculate_step_points(500) == 0

    def test_1000_steps(self):
        assert calculate_step_points(1000) == 10

    def test_5000_steps(self):
        assert calculate_step_points(5000) == 50

    def test_10000_steps(self):
        assert calculate_step_points(10000) == 100

    def test_15000_steps(self):
        assert calculate_step_points(15000) == 150

    def test_20000_steps_cap(self):
        # At cap: 20K steps → 200 points
        assert calculate_step_points(20000) == 200

    def test_exceeds_daily_cap(self):
        # Over cap: still 200 points
        assert calculate_step_points(30000) == 200

    def test_exact_1k_multiples(self):
        for k in range(1, 21):
            assert calculate_step_points(k * 1000) == k * 10

    def test_non_multiple_rounds_down(self):
        assert calculate_step_points(1999) == 10
        assert calculate_step_points(9999) == 90


# ── Step Goal Bonus ─────────────────────────────────────────────────


class TestStepGoalBonus:
    def test_below_goal(self):
        assert calculate_step_goal_bonus(5000) == 0

    def test_at_goal(self):
        assert calculate_step_goal_bonus(10000) == 100

    def test_above_goal(self):
        assert calculate_step_goal_bonus(15000) == 100

    def test_zero_steps(self):
        assert calculate_step_goal_bonus(0) == 0

    def test_just_below_goal(self):
        assert calculate_step_goal_bonus(9999) == 0


# ── Active Minute Points ────────────────────────────────────────────


class TestActiveMinutePoints:
    def test_zero_minutes(self):
        assert calculate_active_minute_points(0, "light") == 0

    def test_negative_minutes(self):
        assert calculate_active_minute_points(-10, "moderate") == 0

    def test_light_intensity(self):
        assert calculate_active_minute_points(30, "light") == 30

    def test_moderate_intensity(self):
        assert calculate_active_minute_points(30, "moderate") == 60

    def test_vigorous_intensity(self):
        assert calculate_active_minute_points(30, "vigorous") == 90

    def test_unknown_intensity_defaults_to_light(self):
        assert calculate_active_minute_points(10, "unknown") == 10

    def test_one_minute_each(self):
        assert calculate_active_minute_points(1, "light") == 1
        assert calculate_active_minute_points(1, "moderate") == 2
        assert calculate_active_minute_points(1, "vigorous") == 3


# ── Workout Bonus ───────────────────────────────────────────────────


class TestWorkoutBonus:
    def test_short_workout_no_bonus(self):
        assert calculate_workout_bonus(15, 0) == 0

    def test_at_minimum_duration(self):
        assert calculate_workout_bonus(20, 0) == 50

    def test_long_workout(self):
        assert calculate_workout_bonus(60, 0) == 50

    def test_first_workout(self):
        assert calculate_workout_bonus(30, 0) == 50

    def test_second_workout(self):
        assert calculate_workout_bonus(30, 1) == 50

    def test_third_workout(self):
        assert calculate_workout_bonus(30, 2) == 50

    def test_fourth_workout_capped(self):
        assert calculate_workout_bonus(30, 3) == 0

    def test_fifth_workout_capped(self):
        assert calculate_workout_bonus(45, 4) == 0


# ── Weekly Streak Bonus ─────────────────────────────────────────────


class TestWeeklyStreakBonus:
    def test_all_active(self):
        assert calculate_weekly_streak_bonus([True] * 7) == 250

    def test_one_missing(self):
        days = [True, True, True, True, True, True, False]
        assert calculate_weekly_streak_bonus(days) == 0

    def test_all_inactive(self):
        assert calculate_weekly_streak_bonus([False] * 7) == 0

    def test_too_few_days(self):
        assert calculate_weekly_streak_bonus([True] * 5) == 0

    def test_empty_list(self):
        assert calculate_weekly_streak_bonus([]) == 0

    def test_more_than_seven_only_last_seven_matter(self):
        days = [False, False, True, True, True, True, True, True, True]
        assert calculate_weekly_streak_bonus(days) == 250

    def test_more_than_seven_last_seven_incomplete(self):
        days = [True, True, True, True, True, True, True, False]
        assert calculate_weekly_streak_bonus(days) == 0


# ── Daily Cap ───────────────────────────────────────────────────────


class TestDailyCap:
    def test_no_points_earned(self):
        assert apply_daily_cap(500, 0) == 500

    def test_partial_cap_remaining(self):
        assert apply_daily_cap(500, 700) == 300

    def test_at_cap(self):
        assert apply_daily_cap(500, 1000) == 0

    def test_over_cap(self):
        assert apply_daily_cap(500, 1200) == 0

    def test_zero_proposed(self):
        assert apply_daily_cap(0, 500) == 0


# ── Calculate Activity Points ───────────────────────────────────────


class TestCalculateActivityPoints:
    def test_steps_activity(self):
        activity = {
            "activity_type": "steps",
            "metrics": {"step_count": 10000},
        }
        points = calculate_activity_points(activity)
        # 10K steps = 100 pts + 100 goal bonus = 200
        assert points == 200

    def test_steps_below_goal(self):
        activity = {
            "activity_type": "steps",
            "metrics": {"step_count": 5000},
        }
        points = calculate_activity_points(activity)
        # 5K steps = 50 pts, no goal bonus
        assert points == 50

    def test_workout_activity_with_bonus(self):
        activity = {
            "activity_type": "workout",
            "duration_minutes": 30,
            "intensity": "moderate",
        }
        ctx = {"workouts_today": 0}
        points = calculate_activity_points(activity, ctx)
        # 50 workout bonus + 30 * 2 moderate = 110
        assert points == 110

    def test_workout_activity_without_bonus_capped(self):
        activity = {
            "activity_type": "workout",
            "duration_minutes": 30,
            "intensity": "moderate",
        }
        ctx = {"workouts_today": 3}
        points = calculate_activity_points(activity, ctx)
        # No workout bonus (capped) + 30 * 2 = 60
        assert points == 60

    def test_workout_short_no_bonus(self):
        activity = {
            "activity_type": "workout",
            "duration_minutes": 15,
            "intensity": "vigorous",
        }
        points = calculate_activity_points(activity)
        # No workout bonus (too short) + 15 * 3 = 45
        assert points == 45

    def test_active_minutes_light(self):
        activity = {
            "activity_type": "active_minutes",
            "duration_minutes": 45,
            "intensity": "light",
        }
        assert calculate_activity_points(activity) == 45

    def test_active_minutes_vigorous(self):
        activity = {
            "activity_type": "active_minutes",
            "duration_minutes": 30,
            "intensity": "vigorous",
        }
        assert calculate_activity_points(activity) == 90

    def test_active_minutes_from_metrics(self):
        activity = {
            "activity_type": "active_minutes",
            "duration_minutes": 0,
            "intensity": "moderate",
            "metrics": {"active_minutes": 20},
        }
        assert calculate_activity_points(activity) == 40

    def test_metrics_as_json_string(self):
        import json

        activity = {
            "activity_type": "steps",
            "metrics": json.dumps({"step_count": 5000}),
        }
        assert calculate_activity_points(activity) == 50

    def test_unknown_activity_type(self):
        activity = {"activity_type": "swimming", "metrics": {}}
        assert calculate_activity_points(activity) == 0


# ── PointsService ───────────────────────────────────────────────────


class MockRepo:
    """Minimal mock repo for testing PointsService."""

    def __init__(self, data=None):
        self.data = data or []
        self.created = []
        self.updated = []

    def find_by_id(self, entity_id):
        for item in self.data:
            if item.get("user_id") == entity_id or item.get("id") == entity_id:
                return item
        return None

    def find_by_user_id(self, user_id):
        return [d for d in self.data if d.get("user_id") == user_id]

    def find_all(self, limit=20, offset=0, filters=None):
        result = self.data
        if filters:
            result = [d for d in result if all(d.get(k) == v for k, v in filters.items())]
        return result[offset : offset + limit]

    def find_by_user_and_date_range(self, user_id, start, end):
        return [d for d in self.data if d.get("user_id") == user_id]

    def create(self, data, new_id=None):
        data["id"] = new_id
        self.created.append(data)
        return new_id

    def update(self, entity_id, data):
        self.updated.append({"id": entity_id, "data": data})
        return 1

    def find_by_field(self, field, value):
        return [d for d in self.data if d.get(field) == value]


class TestPointsService:
    def _make_service(self, user_data=None, txn_data=None, activity_data=None):
        if user_data is None:
            user_data = [{"user_id": "u1", "point_balance": 500}]
        user_repo = MockRepo(user_data)
        txn_repo = MockRepo(txn_data or [])
        activity_repo = MockRepo(activity_data or [])
        return PointsService(
            transaction_repo=txn_repo,
            user_repo=user_repo,
            activity_repo=activity_repo,
        )

    def test_get_balance(self):
        service = self._make_service()
        assert service.get_balance("u1") == 500

    def test_get_balance_user_not_found(self):
        service = self._make_service(user_data=[])
        with pytest.raises(PointsError, match="User not found"):
            service.get_balance("u1")

    def test_create_earn_transaction(self):
        service = self._make_service()
        result = service.create_earn_transaction("u1", 100, "activity", "a1", "test")
        assert result["amount"] == 100
        assert result["balance_after"] == 600

    def test_create_earn_zero_raises(self):
        service = self._make_service()
        with pytest.raises(PointsError, match="positive"):
            service.create_earn_transaction("u1", 0)

    def test_create_earn_negative_raises(self):
        service = self._make_service()
        with pytest.raises(PointsError, match="positive"):
            service.create_earn_transaction("u1", -10)

    def test_create_spend_transaction(self):
        service = self._make_service()
        result = service.create_spend_transaction("u1", 200, "ticket", "t1")
        assert result["amount"] == -200
        assert result["balance_after"] == 300

    def test_create_spend_insufficient_balance(self):
        service = self._make_service()
        with pytest.raises(PointsError, match="Insufficient balance"):
            service.create_spend_transaction("u1", 1000)

    def test_create_adjust_positive(self):
        service = self._make_service()
        result = service.create_adjust_transaction("u1", 200, "admin bonus", "admin1")
        assert result["balance_after"] == 700

    def test_create_adjust_negative(self):
        service = self._make_service()
        result = service.create_adjust_transaction("u1", -200, "penalty", "admin1")
        assert result["balance_after"] == 300

    def test_create_adjust_floors_at_zero(self):
        service = self._make_service()
        result = service.create_adjust_transaction("u1", -1000, "big penalty")
        assert result["balance_after"] == 0

    def test_get_points_earned(self):
        txns = [
            {"user_id": "u1", "transaction_type": "earn", "amount": 100},
            {"user_id": "u1", "transaction_type": "earn", "amount": 200},
            {"user_id": "u1", "transaction_type": "spend", "amount": -50},
        ]
        service = self._make_service(txn_data=txns)
        assert service.get_points_earned("u1") == 300

    def test_award_points_for_steps(self):
        service = self._make_service()
        activity = {
            "activity_id": "a1",
            "activity_type": "steps",
            "metrics": {"step_count": 5000},
        }
        result = service.award_points_for_activity("u1", activity)
        assert result["points_awarded"] == 50

    def test_award_points_daily_cap(self):
        # User already earned 990 today
        from datetime import UTC, datetime

        now = datetime.now(tz=UTC)
        txns = [
            {
                "user_id": "u1",
                "transaction_type": "earn",
                "amount": 990,
                "created_at": now,
            },
        ]
        service = self._make_service(txn_data=txns)
        activity = {
            "activity_id": "a2",
            "activity_type": "steps",
            "metrics": {"step_count": 5000},
        }
        result = service.award_points_for_activity("u1", activity)
        # Would earn 50 but cap at 10 remaining
        assert result["points_awarded"] == 10
        assert result["capped"] is True

    def test_award_points_zero_activity(self):
        service = self._make_service()
        activity = {
            "activity_id": "a3",
            "activity_type": "steps",
            "metrics": {"step_count": 0},
        }
        result = service.award_points_for_activity("u1", activity)
        assert result["points_awarded"] == 0

    def test_get_daily_context(self):
        service = self._make_service()
        ctx = service.get_daily_context("u1")
        assert "points_earned_today" in ctx
        assert "workouts_today" in ctx
        assert "steps_today" in ctx

    def test_check_weekly_streak_no_activities(self):
        service = self._make_service()
        result = service.check_weekly_streak("u1")
        assert "active_days" in result
        assert result["streak_complete"] is False

    def test_transaction_history(self):
        txns = [
            {"user_id": "u1", "transaction_type": "earn", "amount": 100},
            {"user_id": "u1", "transaction_type": "spend", "amount": -50},
            {"user_id": "u2", "transaction_type": "earn", "amount": 200},
        ]
        service = self._make_service(txn_data=txns)
        history = service.get_transaction_history("u1")
        assert len(history) == 2
