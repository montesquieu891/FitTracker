"""Tier engine — enumerate, compute, and validate competition tiers.

FitTrack has 30 tiers: 2 sexes × 5 age brackets × 3 fitness levels.
Tier code format: ``{sex}-{age_bracket}-{fitness_level}``
  e.g. ``M-18-29-BEG``, ``F-40-49-ADV``
"""

from __future__ import annotations

import re
from typing import Any

from fittrack.core.constants import (
    AGE_BRACKETS,
    ALL_TIER_CODES,
    BIOLOGICAL_SEX_TO_CODE,
    FITNESS_LEVEL_NAMES,
    FITNESS_LEVEL_TO_CODE,
    FITNESS_LEVELS,
    SEX_CATEGORIES,
    SEX_CATEGORY_NAMES,
)

# Pre-compiled regex for tier code format validation
_TIER_CODE_RE = re.compile(
    r"^[MF]-\d{2}[-+]\d{0,2}-(?:BEG|INT|ADV)$",
)


def compute_tier_code(
    biological_sex: str,
    age_bracket: str,
    fitness_level: str,
) -> str:
    """Derive tier code from profile field values.

    Args:
        biological_sex: ``"male"`` or ``"female"``
        age_bracket: e.g. ``"18-29"``, ``"30-39"``, ``"60+"``
        fitness_level: ``"beginner"``, ``"intermediate"``, or ``"advanced"``

    Returns:
        Tier code string, e.g. ``"M-18-29-BEG"``

    Raises:
        ValueError: If any input value is invalid.
    """
    sex_code = BIOLOGICAL_SEX_TO_CODE.get(biological_sex)
    if sex_code is None:
        msg = (
            f"Invalid biological_sex: {biological_sex!r}. "
            f"Must be one of: {list(BIOLOGICAL_SEX_TO_CODE.keys())}"
        )
        raise ValueError(msg)

    if age_bracket not in AGE_BRACKETS:
        msg = (
            f"Invalid age_bracket: {age_bracket!r}. "
            f"Must be one of: {AGE_BRACKETS}"
        )
        raise ValueError(msg)

    fl_code = FITNESS_LEVEL_TO_CODE.get(fitness_level)
    if fl_code is None:
        msg = (
            f"Invalid fitness_level: {fitness_level!r}. "
            f"Must be one of: {list(FITNESS_LEVEL_TO_CODE.keys())}"
        )
        raise ValueError(msg)

    return f"{sex_code}-{age_bracket}-{fl_code}"


def validate_tier_code(tier_code: str) -> bool:
    """Check whether *tier_code* is one of the 30 valid codes."""
    return tier_code in ALL_TIER_CODES


def parse_tier_code(tier_code: str) -> dict[str, str]:
    """Parse a tier code into its component parts.

    Returns:
        Dict with keys ``sex``, ``age_bracket``, ``fitness_level`` (all codes).

    Raises:
        ValueError: If the tier code is invalid.
    """
    if not validate_tier_code(tier_code):
        msg = f"Invalid tier code: {tier_code!r}"
        raise ValueError(msg)

    parts = tier_code.split("-", 1)
    sex = parts[0]
    remainder = parts[1]
    # remainder is like "18-29-BEG" or "60+-ADV"
    fl_code = remainder.rsplit("-", 1)[1]
    age_bracket = remainder.rsplit("-", 1)[0]

    return {
        "sex": sex,
        "age_bracket": age_bracket,
        "fitness_level": fl_code,
    }


def get_tier_display_name(tier_code: str) -> str:
    """Human-readable name for a tier code.

    Example: ``"M-18-29-BEG"`` → ``"Male · 18-29 · Beginner"``
    """
    parts = parse_tier_code(tier_code)
    sex_name = SEX_CATEGORY_NAMES.get(parts["sex"], parts["sex"])
    fl_name = FITNESS_LEVEL_NAMES.get(
        parts["fitness_level"], parts["fitness_level"],
    )
    return f"{sex_name} · {parts['age_bracket']} · {fl_name}"


def enumerate_tiers() -> list[dict[str, str]]:
    """Return metadata for all 30 tiers.

    Each item has: ``tier_code``, ``display_name``, ``sex``, ``sex_name``,
    ``age_bracket``, ``fitness_level``, ``fitness_level_name``.
    """
    tiers: list[dict[str, str]] = []
    for sex in SEX_CATEGORIES:
        for age in AGE_BRACKETS:
            for level in FITNESS_LEVELS:
                code = f"{sex}-{age}-{level}"
                tiers.append({
                    "tier_code": code,
                    "display_name": get_tier_display_name(code),
                    "sex": sex,
                    "sex_name": SEX_CATEGORY_NAMES[sex],
                    "age_bracket": age,
                    "fitness_level": level,
                    "fitness_level_name": FITNESS_LEVEL_NAMES[level],
                })
    return tiers


class TierService:
    """Service layer for tier operations requiring database access."""

    def __init__(self, profile_repo: Any) -> None:
        self.profile_repo = profile_repo

    def get_tier_with_user_count(self, tier_code: str) -> dict[str, Any]:
        """Return tier metadata including the number of users in that tier."""
        if not validate_tier_code(tier_code):
            msg = f"Invalid tier code: {tier_code!r}"
            raise ValueError(msg)

        user_count = self.profile_repo.count(filters={"tier_code": tier_code})
        meta = parse_tier_code(tier_code)
        return {
            "tier_code": tier_code,
            "display_name": get_tier_display_name(tier_code),
            "sex": meta["sex"],
            "sex_name": SEX_CATEGORY_NAMES[meta["sex"]],
            "age_bracket": meta["age_bracket"],
            "fitness_level": meta["fitness_level"],
            "fitness_level_name": FITNESS_LEVEL_NAMES[meta["fitness_level"]],
            "user_count": user_count,
        }

    def list_all_tiers_with_counts(self) -> list[dict[str, Any]]:
        """Return all 30 tiers with user counts."""
        result: list[dict[str, Any]] = []
        for tier in enumerate_tiers():
            count = self.profile_repo.count(
                filters={"tier_code": tier["tier_code"]},
            )
            result.append({**tier, "user_count": count})
        return result
