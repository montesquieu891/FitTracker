"""Domain constants for FitTrack."""

from __future__ import annotations

# ── Point Earning Rates ─────────────────────────────────────────────
POINTS_PER_1K_STEPS = 10
STEPS_DAILY_CAP = 20_000  # Max steps that earn points per day

POINTS_ACTIVE_MINUTE_LIGHT = 1
POINTS_ACTIVE_MINUTE_MODERATE = 2
POINTS_ACTIVE_MINUTE_VIGOROUS = 3

POINTS_WORKOUT_BONUS = 50  # Per workout (≥20 min)
WORKOUT_BONUS_DAILY_CAP = 3  # Max workout bonuses per day
WORKOUT_MIN_DURATION_MINUTES = 20

POINTS_DAILY_STEP_GOAL_BONUS = 100  # For hitting 10K steps
DAILY_STEP_GOAL = 10_000

POINTS_WEEKLY_STREAK_BONUS = 250  # 7 consecutive active days
WEEKLY_STREAK_DAYS = 7
ACTIVE_DAY_MIN_MINUTES = 30  # Minimum active minutes to count as "active day"

DAILY_POINT_CAP = 1_000  # Absolute daily maximum

# ── Tier Definitions ────────────────────────────────────────────────
AGE_BRACKETS: list[str] = ["18-29", "30-39", "40-49", "50-59", "60+"]
SEX_CATEGORIES: list[str] = ["M", "F"]
FITNESS_LEVELS: list[str] = ["BEG", "INT", "ADV"]

# Full names for display
FITNESS_LEVEL_NAMES: dict[str, str] = {
    "BEG": "Beginner",
    "INT": "Intermediate",
    "ADV": "Advanced",
}

SEX_CATEGORY_NAMES: dict[str, str] = {
    "M": "Male",
    "F": "Female",
}

# Profile field values → tier code mapping
BIOLOGICAL_SEX_TO_CODE: dict[str, str] = {
    "male": "M",
    "female": "F",
}

FITNESS_LEVEL_TO_CODE: dict[str, str] = {
    "beginner": "BEG",
    "intermediate": "INT",
    "advanced": "ADV",
}

# All 30 valid tier codes
ALL_TIER_CODES: list[str] = [
    f"{sex}-{age}-{level}"
    for sex in SEX_CATEGORIES
    for age in AGE_BRACKETS
    for level in FITNESS_LEVELS
]

# ── Drawing Types ───────────────────────────────────────────────────
DRAWING_TYPES: list[str] = ["daily", "weekly", "monthly", "annual"]

DRAWING_TICKET_COSTS: dict[str, int] = {
    "daily": 100,
    "weekly": 500,
    "monthly": 2_000,
    "annual": 10_000,
}

TICKET_SALES_CLOSE_MINUTES_BEFORE = 5

# ── User Statuses & Roles ──────────────────────────────────────────
USER_STATUSES: list[str] = ["pending", "active", "suspended", "banned"]
USER_ROLES: list[str] = ["user", "premium", "admin"]

# ── Eligible States (US) ───────────────────────────────────────────
# States EXCLUDED from MVP due to sweepstakes law restrictions
EXCLUDED_STATES: set[str] = {"NY", "FL", "RI"}

# All US state abbreviations
ALL_US_STATES: set[str] = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}

ELIGIBLE_STATES: set[str] = ALL_US_STATES - EXCLUDED_STATES

# ── Activity Types ──────────────────────────────────────────────────
ACTIVITY_TYPES: list[str] = ["steps", "workout", "active_minutes"]
INTENSITY_LEVELS: list[str] = ["light", "moderate", "vigorous"]

# ── Tracker Providers ───────────────────────────────────────────────
TRACKER_PROVIDERS: list[str] = ["google_fit", "fitbit"]

# ── Sync Settings ───────────────────────────────────────────────────
SYNC_INTERVAL_MINUTES = 15

# ── Drawing Statuses ────────────────────────────────────────────────
DRAWING_STATUSES: list[str] = ["draft", "scheduled", "open", "closed", "completed", "cancelled"]

# ── Fulfillment Statuses ────────────────────────────────────────────
FULFILLMENT_STATUSES: list[str] = [
    "pending",
    "winner_notified",
    "address_confirmed",
    "address_invalid",
    "shipped",
    "delivered",
    "forfeited",
]

# ── Sponsor Statuses ────────────────────────────────────────────────
SPONSOR_STATUSES: list[str] = ["active", "inactive"]

# ── Transaction Types ───────────────────────────────────────────────
TRANSACTION_TYPES: list[str] = ["earn", "spend", "adjust"]

# ── Notification Types ──────────────────────────────────────────────
NOTIFICATION_TYPES: list[str] = [
    "winner_selected",
    "fulfillment_update",
    "account_status_change",
    "point_adjustment",
    "verification",
    "password_reset",
    "general",
]

# ── Admin Action Types ──────────────────────────────────────────────
ADMIN_ACTION_TYPES: list[str] = [
    "status_change",
    "point_adjustment",
    "role_change",
    "manual_override",
]
