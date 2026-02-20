"""Unit tests for core constants — TDD: validates business rules encoded in constants."""

from __future__ import annotations


class TestPointConstants:
    """Test point calculation constants match business rules."""

    def test_daily_point_cap(self) -> None:
        from fittrack.core.constants import DAILY_POINT_CAP
        assert DAILY_POINT_CAP == 1000

    def test_step_points_rate(self) -> None:
        from fittrack.core.constants import POINTS_PER_1K_STEPS
        assert POINTS_PER_1K_STEPS == 10

    def test_step_daily_cap(self) -> None:
        from fittrack.core.constants import STEPS_DAILY_CAP
        assert STEPS_DAILY_CAP == 20_000

    def test_active_minutes_rates(self) -> None:
        from fittrack.core.constants import (
            POINTS_ACTIVE_MINUTE_LIGHT,
            POINTS_ACTIVE_MINUTE_MODERATE,
            POINTS_ACTIVE_MINUTE_VIGOROUS,
        )
        assert POINTS_ACTIVE_MINUTE_LIGHT == 1
        assert POINTS_ACTIVE_MINUTE_MODERATE == 2
        assert POINTS_ACTIVE_MINUTE_VIGOROUS == 3

    def test_workout_bonus(self) -> None:
        from fittrack.core.constants import POINTS_WORKOUT_BONUS, WORKOUT_BONUS_DAILY_CAP
        assert POINTS_WORKOUT_BONUS == 50
        assert WORKOUT_BONUS_DAILY_CAP == 3

    def test_daily_step_goal_bonus(self) -> None:
        from fittrack.core.constants import POINTS_DAILY_STEP_GOAL_BONUS
        assert POINTS_DAILY_STEP_GOAL_BONUS == 100

    def test_weekly_streak_bonus(self) -> None:
        from fittrack.core.constants import POINTS_WEEKLY_STREAK_BONUS
        assert POINTS_WEEKLY_STREAK_BONUS == 250


class TestTierConstants:
    """Test tier system constants."""

    def test_sex_categories(self) -> None:
        from fittrack.core.constants import SEX_CATEGORIES
        assert set(SEX_CATEGORIES) == {"M", "F"}

    def test_age_brackets(self) -> None:
        from fittrack.core.constants import AGE_BRACKETS
        expected = ["18-29", "30-39", "40-49", "50-59", "60+"]
        assert expected == AGE_BRACKETS

    def test_fitness_levels(self) -> None:
        from fittrack.core.constants import FITNESS_LEVELS
        expected = ["BEG", "INT", "ADV"]
        assert expected == FITNESS_LEVELS

    def test_all_tier_codes_count(self) -> None:
        from fittrack.core.constants import ALL_TIER_CODES
        # 2 sexes x 5 age brackets x 3 fitness levels = 30
        assert len(ALL_TIER_CODES) == 30

    def test_tier_code_format(self) -> None:
        from fittrack.core.constants import ALL_TIER_CODES
        for code in ALL_TIER_CODES:
            parts = code.split("-")
            assert len(parts) >= 3, f"Tier code '{code}' should have at least 3 parts"
            sex_prefix = parts[0]
            assert sex_prefix in ("M", "F"), f"Sex prefix should be M or F, got {sex_prefix}"

    def test_specific_tier_code_exists(self) -> None:
        from fittrack.core.constants import ALL_TIER_CODES
        assert "M-18-29-BEG" in ALL_TIER_CODES
        assert "F-60+-ADV" in ALL_TIER_CODES


class TestStateEligibility:
    """Test state eligibility constants."""

    def test_excluded_states(self) -> None:
        from fittrack.core.constants import EXCLUDED_STATES
        assert {"NY", "FL", "RI"} == EXCLUDED_STATES

    def test_eligible_states_exclude_ny_fl_ri(self) -> None:
        from fittrack.core.constants import ELIGIBLE_STATES
        assert "NY" not in ELIGIBLE_STATES
        assert "FL" not in ELIGIBLE_STATES
        assert "RI" not in ELIGIBLE_STATES

    def test_eligible_states_include_common(self) -> None:
        from fittrack.core.constants import ELIGIBLE_STATES
        for state in ["CA", "TX", "IL", "PA", "OH"]:
            assert state in ELIGIBLE_STATES, f"{state} should be eligible"

    def test_eligible_states_count(self) -> None:
        from fittrack.core.constants import ELIGIBLE_STATES
        # 50 states + DC = 51, minus 3 excluded = 48
        assert len(ELIGIBLE_STATES) == 48


class TestDrawingConstants:
    """Test drawing/sweepstakes constants."""

    def test_drawing_types(self) -> None:
        from fittrack.core.constants import DRAWING_TYPES
        expected = {"daily", "weekly", "monthly", "annual"}
        assert set(DRAWING_TYPES) == expected

    def test_drawing_statuses(self) -> None:
        from fittrack.core.constants import DRAWING_STATUSES
        expected = {"draft", "scheduled", "open", "closed", "completed", "cancelled"}
        assert set(DRAWING_STATUSES) == expected

    def test_ticket_sales_close_minutes(self) -> None:
        from fittrack.core.constants import TICKET_SALES_CLOSE_MINUTES_BEFORE
        assert TICKET_SALES_CLOSE_MINUTES_BEFORE == 5


class TestUserConstants:
    """Test user role and status constants."""

    def test_user_roles(self) -> None:
        from fittrack.core.constants import USER_ROLES
        expected = {"user", "premium", "admin"}
        assert set(USER_ROLES) == expected

    def test_user_statuses(self) -> None:
        from fittrack.core.constants import USER_STATUSES
        expected = {"pending", "active", "suspended", "banned"}
        assert set(USER_STATUSES) == expected


class TestActivityConstants:
    """Test activity type and intensity constants."""

    def test_activity_types(self) -> None:
        from fittrack.core.constants import ACTIVITY_TYPES
        expected = {"steps", "workout", "active_minutes"}
        assert set(ACTIVITY_TYPES) == expected

    def test_intensity_levels(self) -> None:
        from fittrack.core.constants import INTENSITY_LEVELS
        expected = {"light", "moderate", "vigorous"}
        assert set(INTENSITY_LEVELS) == expected

    def test_tracker_providers(self) -> None:
        from fittrack.core.constants import TRACKER_PROVIDERS
        expected = {"google_fit", "fitbit"}
        assert set(TRACKER_PROVIDERS) == expected


class TestTransactionConstants:
    """Test transaction type constants."""

    def test_transaction_types(self) -> None:
        from fittrack.core.constants import TRANSACTION_TYPES
        expected = {"earn", "spend", "adjust"}
        assert set(TRANSACTION_TYPES) == expected


class TestFulfillmentConstants:
    """Test fulfillment status constants."""

    def test_fulfillment_statuses(self) -> None:
        from fittrack.core.constants import FULFILLMENT_STATUSES
        expected = {
            "pending", "winner_notified", "address_confirmed",
            "address_invalid", "shipped", "delivered", "forfeited",
        }
        assert set(FULFILLMENT_STATUSES) == expected
