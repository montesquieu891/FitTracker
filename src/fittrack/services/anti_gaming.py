"""Anti-gaming service — fraud detection and cap enforcement."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.core.constants import (
    DAILY_POINT_CAP,
    WORKOUT_BONUS_DAILY_CAP,
    WORKOUT_MIN_DURATION_MINUTES,
)

logger = logging.getLogger(__name__)


class SuspiciousActivityError(Exception):
    """Raised when suspicious activity is detected."""

    def __init__(self, detail: str, severity: str = "warning") -> None:
        self.detail = detail
        self.severity = severity  # "warning" | "block" | "review"
        super().__init__(detail)


class AntiGamingService:
    """Detects and prevents gaming/abuse of the points system.

    Checks performed:
    1. Daily point cap enforcement
    2. Workout bonus cap enforcement (3/day)
    3. Anomaly detection (>3 std deviations from tier average)
    4. Device verification (multiple accounts per device)
    5. Manual review flagging
    """

    def __init__(
        self,
        activity_repo: Any,
        user_repo: Any,
        transaction_repo: Any,
    ) -> None:
        self.activity_repo = activity_repo
        self.user_repo = user_repo
        self.transaction_repo = transaction_repo

    # ── Cap Enforcement ─────────────────────────────────────────────

    def check_daily_cap(self, user_id: str, proposed_points: int) -> dict[str, Any]:
        """Check if awarding points would exceed the daily cap.

        Returns a dict with:
        - allowed: bool
        - allowed_points: int (clipped to remaining cap)
        - already_earned: int
        - remaining: int
        """
        already_earned = self._get_today_earned(user_id)
        remaining = max(0, DAILY_POINT_CAP - already_earned)
        allowed_points = min(proposed_points, remaining)

        return {
            "allowed": allowed_points > 0,
            "allowed_points": allowed_points,
            "already_earned": already_earned,
            "remaining": remaining,
            "cap": DAILY_POINT_CAP,
        }

    def check_workout_cap(self, user_id: str) -> dict[str, Any]:
        """Check if the user can earn another workout bonus today.

        Returns dict with count and whether another is allowed.
        """
        workouts_today = self._count_today_workouts(user_id)
        return {
            "allowed": workouts_today < WORKOUT_BONUS_DAILY_CAP,
            "workouts_today": workouts_today,
            "cap": WORKOUT_BONUS_DAILY_CAP,
            "remaining": max(0, WORKOUT_BONUS_DAILY_CAP - workouts_today),
        }

    # ── Anomaly Detection ───────────────────────────────────────────

    def detect_anomaly(
        self,
        user_id: str,
        activity: dict[str, Any],
        tier_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Detect anomalous activity based on tier averages.

        An activity is flagged if its value exceeds 3 standard deviations
        from the tier average for that activity type.

        Args:
            user_id: The user performing the activity.
            activity: The activity to check.
            tier_stats: Optional tier-level stats (avg, stddev).
                        If None, anomaly detection is skipped.

        Returns:
            Dict with is_anomaly flag, details, and recommended action.
        """
        if tier_stats is None:
            return {"is_anomaly": False, "reason": "no_tier_stats"}

        activity_type = activity.get("activity_type", "")
        metrics = activity.get("metrics", {})
        if isinstance(metrics, str):
            import json

            try:
                metrics = json.loads(metrics)
            except (json.JSONDecodeError, TypeError):
                metrics = {}

        value = self._extract_primary_value(activity_type, metrics, activity)
        avg = tier_stats.get("avg", 0)
        stddev = tier_stats.get("stddev", 0)

        if stddev <= 0:
            return {"is_anomaly": False, "reason": "insufficient_data"}

        z_score = abs(value - avg) / stddev if stddev > 0 else 0

        is_anomaly = z_score > 3.0
        result: dict[str, Any] = {
            "is_anomaly": is_anomaly,
            "value": value,
            "tier_avg": avg,
            "tier_stddev": stddev,
            "z_score": round(z_score, 2),
        }

        if is_anomaly:
            result["recommended_action"] = "review"
            result["reason"] = (
                f"{activity_type} value {value} is {z_score:.1f} std devs from tier avg {avg}"
            )
            logger.warning("Anomaly detected for user %s: %s", user_id, result["reason"])

        return result

    # ── Device Verification ─────────────────────────────────────────

    def check_device_sharing(
        self,
        device_id: str,
        user_id: str,
        known_devices: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Flag potential multi-account device sharing.

        Args:
            device_id: Device identifier from the tracker.
            user_id: Current user.
            known_devices: List of {user_id, device_id} records.
        """
        if not known_devices or not device_id:
            return {"suspicious": False, "reason": "no_device_data"}

        other_users = [
            d["user_id"]
            for d in known_devices
            if d.get("device_id") == device_id and d.get("user_id") != user_id
        ]

        if other_users:
            return {
                "suspicious": True,
                "reason": f"Device shared with {len(other_users)} other account(s)",
                "other_user_count": len(other_users),
                "recommended_action": "review",
            }

        return {"suspicious": False}

    # ── Review Queue ────────────────────────────────────────────────

    def flag_for_review(
        self,
        user_id: str,
        reason: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Flag a user for manual review.

        In MVP, this logs and returns a flag record. A full review queue
        table could be added later.
        """
        flag = {
            "user_id": user_id,
            "reason": reason,
            "details": details or {},
            "flagged_at": datetime.now(tz=UTC).isoformat(),
            "status": "pending_review",
        }
        logger.warning("User flagged for review: %s — %s", user_id, reason)
        return flag

    def run_all_checks(
        self,
        user_id: str,
        activity: dict[str, Any],
        proposed_points: int,
        tier_stats: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run all anti-gaming checks for an activity.

        Returns a combined result with:
        - allowed: bool (should points be awarded?)
        - allowed_points: int (possibly capped)
        - flags: list of issues found
        """
        flags: list[str] = []

        # Daily cap
        cap_result = self.check_daily_cap(user_id, proposed_points)
        allowed_points = cap_result["allowed_points"]
        if not cap_result["allowed"]:
            flags.append("daily_cap_reached")

        # Workout cap
        if activity.get("activity_type") == "workout":
            workout_result = self.check_workout_cap(user_id)
            if not workout_result["allowed"]:
                flags.append("workout_cap_reached")
                allowed_points = 0

        # Anomaly detection
        anomaly_result = self.detect_anomaly(user_id, activity, tier_stats)
        if anomaly_result.get("is_anomaly"):
            flags.append(f"anomaly: {anomaly_result.get('reason', '')}")
            # Don't block, but flag for review
            self.flag_for_review(
                user_id,
                "anomalous_activity",
                {"activity": activity, "anomaly": anomaly_result},
            )

        return {
            "allowed": allowed_points > 0 and "workout_cap_reached" not in flags,
            "allowed_points": allowed_points,
            "flags": flags,
            "cap_status": cap_result,
        }

    # ── Private helpers ─────────────────────────────────────────────

    def _get_today_earned(self, user_id: str) -> int:
        """Sum of points earned today from transactions."""
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        all_txns = self.transaction_repo.find_by_user_id(user_id)
        total = 0
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
                total += txn.get("amount", 0)
        return total

    def _count_today_workouts(self, user_id: str) -> int:
        """Count workout bonuses already awarded today."""
        today_start = datetime.now(tz=UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        try:
            activities = self.activity_repo.find_by_user_and_date_range(
                user_id, today_start, today_end
            )
        except Exception:
            return 0

        return sum(
            1
            for a in activities
            if a.get("activity_type") == "workout"
            and (a.get("duration_minutes") or 0) >= WORKOUT_MIN_DURATION_MINUTES
            and a.get("points_earned", 0) > 0
        )

    @staticmethod
    def _extract_primary_value(
        activity_type: str,
        metrics: dict[str, Any],
        activity: dict[str, Any],
    ) -> float:
        """Extract the primary numeric value for anomaly comparison."""
        if activity_type == "steps":
            return float(metrics.get("step_count", 0))
        if activity_type == "workout":
            return float(activity.get("duration_minutes", 0) or 0)
        if activity_type == "active_minutes":
            return float(activity.get("duration_minutes", 0) or metrics.get("active_minutes", 0))
        return 0.0


def compute_tier_stats(
    activities: list[dict[str, Any]],
    activity_type: str,
) -> dict[str, float]:
    """Compute mean and standard deviation for a set of activities.

    Used to establish tier-level baselines for anomaly detection.
    """
    values: list[float] = []
    for a in activities:
        if a.get("activity_type") != activity_type:
            continue
        metrics = a.get("metrics", {})
        if isinstance(metrics, str):
            import json

            try:
                metrics = json.loads(metrics)
            except (json.JSONDecodeError, TypeError):
                metrics = {}

        if activity_type == "steps":
            values.append(float(metrics.get("step_count", 0)))
        elif activity_type == "workout":
            values.append(float(a.get("duration_minutes", 0) or 0))
        elif activity_type == "active_minutes":
            dur = a.get("duration_minutes", 0) or metrics.get("active_minutes", 0)
            values.append(float(dur))

    if not values:
        return {"avg": 0.0, "stddev": 0.0, "count": 0}

    avg = sum(values) / len(values)
    variance = sum((v - avg) ** 2 for v in values) / len(values)
    stddev = math.sqrt(variance)

    return {"avg": round(avg, 2), "stddev": round(stddev, 2), "count": len(values)}
