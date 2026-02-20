"""Hypothesis property-based tests for the points engine."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from fittrack.core.constants import (
    DAILY_POINT_CAP,
    POINTS_ACTIVE_MINUTE_LIGHT,
    POINTS_ACTIVE_MINUTE_MODERATE,
    POINTS_ACTIVE_MINUTE_VIGOROUS,
    POINTS_PER_1K_STEPS,
    POINTS_WORKOUT_BONUS,
    STEPS_DAILY_CAP,
    WORKOUT_BONUS_DAILY_CAP,
)
from fittrack.services.points import (
    apply_daily_cap,
    calculate_active_minute_points,
    calculate_activity_points,
    calculate_step_points,
    calculate_weekly_streak_bonus,
    calculate_workout_bonus,
)

# ── Step Points Properties ──────────────────────────────────────────


@given(steps=st.integers(min_value=0, max_value=100_000))
@settings(max_examples=200)
def test_step_points_non_negative(steps: int):
    """Step points are always >= 0."""
    assert calculate_step_points(steps) >= 0


@given(steps=st.integers(min_value=0, max_value=100_000))
@settings(max_examples=200)
def test_step_points_capped(steps: int):
    """Step points never exceed the cap (20K steps * 10/1K = 200)."""
    max_points = (STEPS_DAILY_CAP // 1000) * POINTS_PER_1K_STEPS
    assert calculate_step_points(steps) <= max_points


@given(steps=st.integers(min_value=0, max_value=100_000))
@settings(max_examples=200)
def test_step_points_monotonic(steps: int):
    """More steps never result in fewer points."""
    if steps >= 1000:
        assert calculate_step_points(steps) >= calculate_step_points(steps - 1000)


# ── Active Minute Properties ───────────────────────────────────────


@given(
    minutes=st.integers(min_value=0, max_value=1440),
    intensity=st.sampled_from(["light", "moderate", "vigorous"]),
)
@settings(max_examples=200)
def test_active_minute_points_non_negative(minutes: int, intensity: str):
    assert calculate_active_minute_points(minutes, intensity) >= 0


@given(minutes=st.integers(min_value=1, max_value=1440))
@settings(max_examples=100)
def test_vigorous_more_than_light(minutes: int):
    """Vigorous intensity always earns more than light."""
    light = calculate_active_minute_points(minutes, "light")
    vigorous = calculate_active_minute_points(minutes, "vigorous")
    assert vigorous > light


@given(minutes=st.integers(min_value=1, max_value=1440))
@settings(max_examples=100)
def test_intensity_ordering(minutes: int):
    """light < moderate < vigorous for same minutes."""
    light = calculate_active_minute_points(minutes, "light")
    moderate = calculate_active_minute_points(minutes, "moderate")
    vigorous = calculate_active_minute_points(minutes, "vigorous")
    assert light <= moderate <= vigorous
    assert light == minutes * POINTS_ACTIVE_MINUTE_LIGHT
    assert moderate == minutes * POINTS_ACTIVE_MINUTE_MODERATE
    assert vigorous == minutes * POINTS_ACTIVE_MINUTE_VIGOROUS


# ── Workout Bonus Properties ───────────────────────────────────────


@given(
    duration=st.integers(min_value=0, max_value=300),
    workouts_today=st.integers(min_value=0, max_value=10),
)
@settings(max_examples=200)
def test_workout_bonus_bounded(duration: int, workouts_today: int):
    """Workout bonus is either 0 or exactly POINTS_WORKOUT_BONUS."""
    bonus = calculate_workout_bonus(duration, workouts_today)
    assert bonus in (0, POINTS_WORKOUT_BONUS)


@given(workouts_today=st.integers(min_value=WORKOUT_BONUS_DAILY_CAP, max_value=20))
@settings(max_examples=50)
def test_workout_cap_always_blocks(workouts_today: int):
    """Once at the daily workout cap, bonus is always 0."""
    assert calculate_workout_bonus(60, workouts_today) == 0


# ── Weekly Streak Properties ───────────────────────────────────────


@given(days=st.lists(st.booleans(), min_size=7, max_size=14))
@settings(max_examples=200)
def test_streak_bonus_binary(days: list[bool]):
    """Streak bonus is either 0 or 250."""
    bonus = calculate_weekly_streak_bonus(days)
    assert bonus in (0, 250)


@given(extra=st.lists(st.booleans(), min_size=0, max_size=7))
@settings(max_examples=50)
def test_seven_true_always_gets_bonus(extra: list[bool]):
    """If the last 7 days are all active, bonus is awarded."""
    days = extra + [True] * 7
    assert calculate_weekly_streak_bonus(days) == 250


# ── Daily Cap Properties ───────────────────────────────────────────


@given(
    points=st.integers(min_value=0, max_value=5000),
    already=st.integers(min_value=0, max_value=5000),
)
@settings(max_examples=200)
def test_daily_cap_never_exceeds_limit(points: int, already: int):
    """After applying daily cap, total never exceeds DAILY_POINT_CAP."""
    capped = apply_daily_cap(points, already)
    assert already + capped <= max(already, DAILY_POINT_CAP)


@given(
    points=st.integers(min_value=0, max_value=5000),
    already=st.integers(min_value=0, max_value=5000),
)
@settings(max_examples=200)
def test_daily_cap_non_negative(points: int, already: int):
    """Capped points are never negative."""
    assert apply_daily_cap(points, already) >= 0


@given(points=st.integers(min_value=0, max_value=1000))
@settings(max_examples=100)
def test_daily_cap_identity_when_no_prior(points: int):
    """With nothing earned yet and points <= cap, full amount passes through."""
    assert apply_daily_cap(points, 0) == points


# ── Activity Points Properties ──────────────────────────────────────


@given(step_count=st.integers(min_value=0, max_value=50000))
@settings(max_examples=100)
def test_activity_points_steps_non_negative(step_count: int):
    activity = {"activity_type": "steps", "metrics": {"step_count": step_count}}
    assert calculate_activity_points(activity) >= 0


@given(
    duration=st.integers(min_value=0, max_value=300),
    intensity=st.sampled_from(["light", "moderate", "vigorous"]),
)
@settings(max_examples=100)
def test_activity_points_workout_non_negative(duration: int, intensity: str):
    activity = {
        "activity_type": "workout",
        "duration_minutes": duration,
        "intensity": intensity,
    }
    assert calculate_activity_points(activity) >= 0
