"""Points calculation engine — rate tables, daily caps, bonuses."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.core.constants import (
    ACTIVE_DAY_MIN_MINUTES,
    DAILY_POINT_CAP,
    DAILY_STEP_GOAL,
    POINTS_ACTIVE_MINUTE_LIGHT,
    POINTS_ACTIVE_MINUTE_MODERATE,
    POINTS_ACTIVE_MINUTE_VIGOROUS,
    POINTS_DAILY_STEP_GOAL_BONUS,
    POINTS_PER_1K_STEPS,
    POINTS_WEEKLY_STREAK_BONUS,
    POINTS_WORKOUT_BONUS,
    STEPS_DAILY_CAP,
    WEEKLY_STREAK_DAYS,
    WORKOUT_BONUS_DAILY_CAP,
    WORKOUT_MIN_DURATION_MINUTES,
)

logger = logging.getLogger(__name__)


class PointsError(Exception):
    """Points calculation or transaction error."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Rate Table Calculators ──────────────────────────────────────────


def calculate_step_points(step_count: int) -> int:
    """Calculate points earned from steps.

    Rate: 10 points per 1,000 steps.
    Cap: 20,000 steps/day max (200 points).
    """
    if step_count <= 0:
        return 0
    capped_steps = min(step_count, STEPS_DAILY_CAP)
    return (capped_steps // 1000) * POINTS_PER_1K_STEPS


def calculate_step_goal_bonus(step_count: int) -> int:
    """100-point bonus for hitting 10K steps in a day."""
    if step_count >= DAILY_STEP_GOAL:
        return POINTS_DAILY_STEP_GOAL_BONUS
    return 0


def calculate_active_minute_points(
    minutes: int,
    intensity: str,
) -> int:
    """Calculate points from active minutes.

    Rates: light=1, moderate=2, vigorous=3 per minute.
    """
    if minutes <= 0:
        return 0

    rate_map = {
        "light": POINTS_ACTIVE_MINUTE_LIGHT,
        "moderate": POINTS_ACTIVE_MINUTE_MODERATE,
        "vigorous": POINTS_ACTIVE_MINUTE_VIGOROUS,
    }
    rate = rate_map.get(intensity, POINTS_ACTIVE_MINUTE_LIGHT)
    return minutes * rate


def calculate_workout_bonus(
    duration_minutes: int,
    workouts_today: int,
) -> int:
    """50-point bonus per workout (≥20 min), max 3/day.

    Args:
        duration_minutes: Length of the workout.
        workouts_today: Number of workout bonuses already awarded today.
    """
    if duration_minutes < WORKOUT_MIN_DURATION_MINUTES:
        return 0
    if workouts_today >= WORKOUT_BONUS_DAILY_CAP:
        return 0
    return POINTS_WORKOUT_BONUS


def calculate_weekly_streak_bonus(
    active_days: list[bool],
) -> int:
    """250-point bonus for 7 consecutive active days.

    Args:
        active_days: List of 7 booleans (oldest → newest). An "active day"
                     has ≥30 minutes of activity.
    """
    if len(active_days) < WEEKLY_STREAK_DAYS:
        return 0
    # Check the last 7 days
    last_seven = active_days[-WEEKLY_STREAK_DAYS:]
    if all(last_seven):
        return POINTS_WEEKLY_STREAK_BONUS
    return 0


def apply_daily_cap(points: int, already_earned_today: int) -> int:
    """Enforce 1,000 point daily maximum.

    Returns the clamped points value.
    """
    remaining = max(0, DAILY_POINT_CAP - already_earned_today)
    return min(points, remaining)


# ── Activity → Points Calculation ───────────────────────────────────


def calculate_activity_points(
    activity: dict[str, Any],
    daily_context: dict[str, Any] | None = None,
) -> int:
    """Calculate points for a single activity.

    Args:
        activity: Activity dict with type, metrics, duration, intensity.
        daily_context: Optional context about what's already been earned
                       today (for cap enforcement). Keys:
                       - points_earned_today: int
                       - workouts_today: int
                       - steps_today: int

    Returns:
        Points earned (before daily cap application — use apply_daily_cap separately).
    """
    ctx = daily_context or {}
    activity_type = activity.get("activity_type", "")
    metrics = activity.get("metrics", {})
    if isinstance(metrics, str):
        import json
        try:
            metrics = json.loads(metrics)
        except (json.JSONDecodeError, TypeError):
            metrics = {}

    points = 0

    if activity_type == "steps":
        step_count = metrics.get("step_count", 0)
        points += calculate_step_points(step_count)
        points += calculate_step_goal_bonus(step_count)

    elif activity_type == "workout":
        duration = activity.get("duration_minutes", 0) or 0
        workouts_today = ctx.get("workouts_today", 0)
        points += calculate_workout_bonus(duration, workouts_today)

        # Also earn active minute points for workout duration
        intensity = activity.get("intensity", "moderate")
        if duration > 0 and intensity:
            points += calculate_active_minute_points(duration, intensity)

    elif activity_type == "active_minutes":
        minutes = activity.get("duration_minutes", 0) or 0
        if minutes == 0:
            minutes = metrics.get("active_minutes", 0)
        intensity = activity.get("intensity", "moderate")
        points += calculate_active_minute_points(minutes, intensity)

    return points


# ── Points Service ──────────────────────────────────────────────────


class PointsService:
    """Manages point calculations, transactions, and balance updates.

    Receives repositories via __init__ — no global state.
    """

    def __init__(
        self,
        transaction_repo: Any,
        user_repo: Any,
        activity_repo: Any,
        daily_log_repo: Any = None,
    ) -> None:
        self.transaction_repo = transaction_repo
        self.user_repo = user_repo
        self.activity_repo = activity_repo
        self.daily_log_repo = daily_log_repo

    def award_points_for_activity(
        self,
        user_id: str,
        activity: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate and award points for a single activity.

        Enforces daily cap. Creates a point transaction.
        Returns the transaction details.
        """
        # Get daily context
        daily_ctx = self.get_daily_context(user_id)

        # Calculate raw points
        raw_points = calculate_activity_points(activity, daily_ctx)
        if raw_points <= 0:
            return {"points_awarded": 0, "reason": "no_points_earned"}

        # Apply daily cap
        capped_points = apply_daily_cap(raw_points, daily_ctx.get("points_earned_today", 0))
        if capped_points <= 0:
            return {"points_awarded": 0, "reason": "daily_cap_reached"}

        # Create transaction and update balance
        transaction = self.create_earn_transaction(
            user_id=user_id,
            amount=capped_points,
            reference_type="activity",
            reference_id=activity.get("activity_id", ""),
            description=f"Points for {activity.get('activity_type', 'activity')}",
        )

        # Update daily log
        self._update_daily_log(user_id, capped_points, activity)

        return {
            "points_awarded": capped_points,
            "raw_points": raw_points,
            "capped": capped_points < raw_points,
            "transaction_id": transaction.get("transaction_id"),
        }

    def create_earn_transaction(
        self,
        user_id: str,
        amount: int,
        reference_type: str = "",
        reference_id: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """Create an earn transaction and update user balance.

        Uses optimistic locking on point_balance.
        """
        if amount <= 0:
            raise PointsError("Earn amount must be positive")

        # Get current balance
        current_balance = self._get_balance(user_id)
        new_balance = current_balance + amount

        # Create transaction
        txn_id = uuid.uuid4().hex
        txn_data = {
            "user_id": user_id,
            "transaction_type": "earn",
            "amount": amount,
            "balance_after": new_balance,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": description,
            "created_at": datetime.now(tz=UTC),
        }
        self.transaction_repo.create(data=txn_data, new_id=txn_id)

        # Update user balance
        self._update_balance(user_id, new_balance)

        return {"transaction_id": txn_id, "amount": amount, "balance_after": new_balance}

    def create_spend_transaction(
        self,
        user_id: str,
        amount: int,
        reference_type: str = "",
        reference_id: str = "",
        description: str = "",
    ) -> dict[str, Any]:
        """Create a spend transaction — deducts from balance.

        Validates sufficient balance. Uses optimistic locking.
        """
        if amount <= 0:
            raise PointsError("Spend amount must be positive")

        current_balance = self._get_balance(user_id)
        if current_balance < amount:
            raise PointsError(
                f"Insufficient balance: {current_balance} < {amount}",
                status_code=400,
            )

        new_balance = current_balance - amount

        txn_id = uuid.uuid4().hex
        txn_data = {
            "user_id": user_id,
            "transaction_type": "spend",
            "amount": -amount,
            "balance_after": new_balance,
            "reference_type": reference_type,
            "reference_id": reference_id,
            "description": description,
            "created_at": datetime.now(tz=UTC),
        }
        self.transaction_repo.create(data=txn_data, new_id=txn_id)
        self._update_balance(user_id, new_balance)

        return {"transaction_id": txn_id, "amount": -amount, "balance_after": new_balance}

    def create_adjust_transaction(
        self,
        user_id: str,
        amount: int,
        description: str = "",
        admin_id: str = "",
    ) -> dict[str, Any]:
        """Admin point adjustment — can be positive or negative."""
        current_balance = self._get_balance(user_id)
        new_balance = max(0, current_balance + amount)

        txn_id = uuid.uuid4().hex
        txn_data = {
            "user_id": user_id,
            "transaction_type": "adjust",
            "amount": amount,
            "balance_after": new_balance,
            "reference_type": "admin_adjustment",
            "reference_id": admin_id,
            "description": description,
            "created_at": datetime.now(tz=UTC),
        }
        self.transaction_repo.create(data=txn_data, new_id=txn_id)
        self._update_balance(user_id, new_balance)

        return {"transaction_id": txn_id, "amount": amount, "balance_after": new_balance}

    def get_balance(self, user_id: str) -> int:
        """Get current point balance for a user."""
        return self._get_balance(user_id)

    def get_points_earned(self, user_id: str) -> int:
        """Get total points ever earned (for leaderboard ranking)."""
        transactions = self.transaction_repo.find_by_user_id(user_id)
        return sum(
            t.get("amount", 0)
            for t in transactions
            if t.get("transaction_type") == "earn"
        )

    def get_transaction_history(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get paginated transaction history for a user."""
        return self.transaction_repo.find_all(
            limit=limit,
            offset=offset,
            filters={"user_id": user_id},
        )

    def get_daily_context(self, user_id: str) -> dict[str, Any]:
        """Build a context dict with today's point/activity state.

        Used for daily cap enforcement and workout bonus limits.
        """
        today_start = datetime.now(tz=UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        today_end = today_start + timedelta(days=1)

        # Get today's transactions
        all_txns = self.transaction_repo.find_by_user_id(user_id)
        today_earned = 0
        for txn in all_txns:
            if txn.get("transaction_type") != "earn":
                continue
            created = txn.get("created_at")
            if created is None:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except ValueError:
                    continue
            if hasattr(created, "tzinfo") and created.tzinfo is None:
                created = created.replace(tzinfo=UTC)
            if today_start <= created < today_end:
                today_earned += txn.get("amount", 0)

        # Get today's activities for workout count
        try:
            today_activities = self.activity_repo.find_by_user_and_date_range(
                user_id, today_start, today_end
            )
        except Exception:
            today_activities = []

        workouts_today = sum(
            1
            for a in today_activities
            if a.get("activity_type") == "workout"
            and (a.get("duration_minutes") or 0) >= WORKOUT_MIN_DURATION_MINUTES
            and a.get("points_earned", 0) > 0
        )

        steps_today = 0
        for a in today_activities:
            if a.get("activity_type") == "steps":
                metrics = a.get("metrics", {})
                if isinstance(metrics, str):
                    import json
                    try:
                        metrics = json.loads(metrics)
                    except (json.JSONDecodeError, TypeError):
                        metrics = {}
                steps_today += metrics.get("step_count", 0)

        return {
            "points_earned_today": today_earned,
            "workouts_today": workouts_today,
            "steps_today": steps_today,
        }

    def check_weekly_streak(self, user_id: str) -> dict[str, Any]:
        """Check if user qualifies for a weekly streak bonus.

        Returns streak status and whether bonus was awarded.
        """
        now = datetime.now(tz=UTC)
        active_days: list[bool] = []

        for i in range(WEEKLY_STREAK_DAYS):
            day = now - timedelta(days=WEEKLY_STREAK_DAYS - 1 - i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)

            try:
                day_activities = self.activity_repo.find_by_user_and_date_range(
                    user_id, day_start, day_end
                )
            except Exception:
                day_activities = []

            total_active_minutes = 0
            for a in day_activities:
                if a.get("activity_type") in ("active_minutes", "workout"):
                    total_active_minutes += a.get("duration_minutes", 0) or 0

            active_days.append(total_active_minutes >= ACTIVE_DAY_MIN_MINUTES)

        bonus = calculate_weekly_streak_bonus(active_days)
        return {
            "active_days": active_days,
            "streak_complete": all(active_days),
            "bonus_points": bonus,
        }

    # ── Private helpers ─────────────────────────────────────────────

    def _get_balance(self, user_id: str) -> int:
        """Get current balance from user record."""
        user = self.user_repo.find_by_id(user_id)
        if not user:
            raise PointsError("User not found", status_code=404)
        return int(user.get("point_balance", 0))

    def _update_balance(self, user_id: str, new_balance: int) -> None:
        """Update user point balance."""
        self.user_repo.update(user_id, {"point_balance": new_balance})

    def _update_daily_log(
        self,
        user_id: str,
        points: int,
        activity: dict[str, Any],
    ) -> None:
        """Update the daily points log for cap tracking."""
        if self.daily_log_repo is None:
            return

        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        try:
            existing = self.daily_log_repo.find_by_field("user_id", user_id)
            today_log = None
            for log in existing:
                if str(log.get("log_date", ""))[:10] == today:
                    today_log = log
                    break

            if today_log:
                log_id = today_log.get("log_id", "")
                new_total = today_log.get("total_points", 0) + points
                activity_type = activity.get("activity_type", "")
                update_data: dict[str, Any] = {"total_points": new_total}
                if activity_type == "steps":
                    update_data["step_points"] = today_log.get("step_points", 0) + points
                elif activity_type == "workout":
                    update_data["workout_points"] = today_log.get("workout_points", 0) + points
                    update_data["workout_count"] = today_log.get("workout_count", 0) + 1
                elif activity_type == "active_minutes":
                    update_data["active_minute_points"] = (
                        today_log.get("active_minute_points", 0) + points
                    )
                self.daily_log_repo.update(log_id, update_data)
            else:
                log_id = uuid.uuid4().hex
                log_data: dict[str, Any] = {
                    "user_id": user_id,
                    "log_date": today,
                    "total_points": points,
                    "step_points": points if activity.get("activity_type") == "steps" else 0,
                    "workout_points": (
                        points if activity.get("activity_type") == "workout" else 0
                    ),
                    "workout_count": (
                        1 if activity.get("activity_type") == "workout" else 0
                    ),
                    "active_minute_points": (
                        points if activity.get("activity_type") == "active_minutes" else 0
                    ),
                    "bonus_points": 0,
                }
                self.daily_log_repo.create(data=log_data, new_id=log_id)
        except Exception:
            logger.warning("Failed to update daily log for user %s", user_id, exc_info=True)
