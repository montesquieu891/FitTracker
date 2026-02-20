"""Synthetic data factories for testing — generates realistic fake data."""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from faker import Faker

from fittrack.core.constants import (
    ACTIVITY_TYPES,
    AGE_BRACKETS,
    BIOLOGICAL_SEX_TO_CODE,
    DRAWING_TYPES,
    ELIGIBLE_STATES,
    FITNESS_LEVEL_TO_CODE,
    FITNESS_LEVELS,
    INTENSITY_LEVELS,
    TRACKER_PROVIDERS,
    TRANSACTION_TYPES,
    USER_STATUSES,
)

fake = Faker()
Faker.seed(42)
random.seed(42)


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


# ── User Factory ────────────────────────────────────────────────────

def build_user(**overrides: Any) -> dict[str, Any]:
    """Generate a synthetic user dict."""
    data: dict[str, Any] = {
        "user_id": _uuid(),
        "email": fake.unique.email(),
        "password_hash": fake.sha256(),
        "email_verified": random.choice([True, False]),
        "status": random.choice(USER_STATUSES),
        "role": "user",
        "point_balance": random.randint(0, 5000),
        "points_earned_total": random.randint(0, 50000),
        "created_at": _now() - timedelta(days=random.randint(1, 365)),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data


def build_user_batch(count: int = 10, **overrides: Any) -> list[dict[str, Any]]:
    """Generate multiple synthetic users."""
    return [build_user(**overrides) for _ in range(count)]


# ── Profile Factory ─────────────────────────────────────────────────

def build_profile(user_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a synthetic profile dict."""
    sex = random.choice(["male", "female"])
    sex_code = BIOLOGICAL_SEX_TO_CODE[sex]
    age_bracket = random.choice(AGE_BRACKETS)
    fitness_level_code = random.choice(FITNESS_LEVELS)
    fitness_level_name = {v: k for k, v in FITNESS_LEVEL_TO_CODE.items()}.get(
        fitness_level_code, "beginner"
    )
    tier_code = f"{sex_code}-{age_bracket}-{fitness_level_code}"

    eligible = list(ELIGIBLE_STATES)
    data: dict[str, Any] = {
        "profile_id": _uuid(),
        "user_id": user_id or _uuid(),
        "display_name": fake.user_name()[:50],
        "date_of_birth": fake.date_of_birth(minimum_age=18, maximum_age=80),
        "state_of_residence": random.choice(eligible),
        "biological_sex": sex,
        "age_bracket": age_bracket,
        "fitness_level": fitness_level_name,
        "tier_code": tier_code,
        "height_inches": random.randint(60, 78),
        "weight_pounds": random.randint(110, 280),
        "goals": ["lose_weight", "build_muscle"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data


# ── Activity Factory ────────────────────────────────────────────────

def build_activity(user_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a synthetic activity dict."""
    start = _now() - timedelta(hours=random.randint(1, 48))
    duration = random.randint(10, 90)
    data: dict[str, Any] = {
        "activity_id": _uuid(),
        "user_id": user_id or _uuid(),
        "external_id": _uuid(),
        "activity_type": random.choice(ACTIVITY_TYPES),
        "start_time": start,
        "end_time": start + timedelta(minutes=duration),
        "duration_minutes": duration,
        "intensity": random.choice(INTENSITY_LEVELS),
        "metrics": {"calories": random.randint(50, 800), "steps": random.randint(0, 15000)},
        "points_earned": random.randint(0, 200),
        "processed": True,
        "created_at": _now(),
    }
    data.update(overrides)
    return data


# ── Tracker Connection Factory ──────────────────────────────────────

def build_connection(user_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a synthetic tracker connection dict."""
    data: dict[str, Any] = {
        "connection_id": _uuid(),
        "user_id": user_id or _uuid(),
        "provider": random.choice(TRACKER_PROVIDERS),
        "is_primary": True,
        "access_token": fake.sha256(),
        "refresh_token": fake.sha256(),
        "token_expires_at": _now() + timedelta(hours=1),
        "last_sync_at": _now() - timedelta(minutes=random.randint(5, 60)),
        "sync_status": "success",
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data


# ── Point Transaction Factory ───────────────────────────────────────

def build_transaction(user_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a synthetic point transaction dict."""
    amount = random.randint(10, 500)
    data: dict[str, Any] = {
        "transaction_id": _uuid(),
        "user_id": user_id or _uuid(),
        "transaction_type": random.choice(TRANSACTION_TYPES),
        "amount": amount,
        "balance_after": random.randint(0, 5000),
        "reference_type": "activity",
        "reference_id": _uuid(),
        "description": "Points earned from steps",
        "created_at": _now(),
    }
    data.update(overrides)
    return data


# ── Drawing Factory ─────────────────────────────────────────────────

def build_drawing(**overrides: Any) -> dict[str, Any]:
    """Generate a synthetic drawing dict."""
    draw_type = random.choice(DRAWING_TYPES)
    draw_time = _now() + timedelta(days=random.randint(1, 30))
    data: dict[str, Any] = {
        "drawing_id": _uuid(),
        "drawing_type": draw_type,
        "name": f"{draw_type.capitalize()} Drawing - {fake.date()}",
        "description": fake.sentence(),
        "ticket_cost_points": random.choice([100, 500, 2000, 10000]),
        "drawing_time": draw_time,
        "ticket_sales_close": draw_time - timedelta(minutes=5),
        "status": "draft",
        "total_tickets": 0,
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data


# ── Ticket Factory ──────────────────────────────────────────────────

def build_ticket(
    drawing_id: str | None = None,
    user_id: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Generate a synthetic ticket dict."""
    data: dict[str, Any] = {
        "ticket_id": _uuid(),
        "drawing_id": drawing_id or _uuid(),
        "user_id": user_id or _uuid(),
        "ticket_number": random.randint(1, 9999),
        "is_winner": False,
        "created_at": _now(),
    }
    data.update(overrides)
    return data


# ── Prize Factory ───────────────────────────────────────────────────

def build_prize(drawing_id: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Generate a synthetic prize dict."""
    data: dict[str, Any] = {
        "prize_id": _uuid(),
        "drawing_id": drawing_id or _uuid(),
        "sponsor_id": _uuid(),
        "rank": random.randint(1, 5),
        "name": fake.bs().title(),
        "description": fake.sentence(),
        "value_usd": round(random.uniform(5.0, 500.0), 2),
        "quantity": 1,
        "fulfillment_type": random.choice(["digital", "physical"]),
        "created_at": _now(),
    }
    data.update(overrides)
    return data


# ── Sponsor Factory ─────────────────────────────────────────────────

def build_sponsor(**overrides: Any) -> dict[str, Any]:
    """Generate a synthetic sponsor dict."""
    data: dict[str, Any] = {
        "sponsor_id": _uuid(),
        "name": fake.company(),
        "contact_name": fake.name(),
        "contact_email": fake.company_email(),
        "contact_phone": fake.phone_number(),
        "website_url": fake.url(),
        "logo_url": fake.image_url(),
        "status": "active",
        "notes": fake.sentence(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data


# ── Fulfillment Factory ────────────────────────────────────────────

def build_fulfillment(
    ticket_id: str | None = None,
    prize_id: str | None = None,
    user_id: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    """Generate a synthetic fulfillment dict."""
    data: dict[str, Any] = {
        "fulfillment_id": _uuid(),
        "ticket_id": ticket_id or _uuid(),
        "prize_id": prize_id or _uuid(),
        "user_id": user_id or _uuid(),
        "status": "pending",
        "shipping_address": {
            "street": fake.street_address(),
            "city": fake.city(),
            "state": fake.state_abbr(),
            "zip": fake.zipcode(),
        },
        "created_at": _now(),
        "updated_at": _now(),
    }
    data.update(overrides)
    return data
