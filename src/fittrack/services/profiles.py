"""Profile service — business logic for user profiles.

Handles profile CRUD, tier computation, tier recalculation on field changes,
and profile completion checks.
"""

from __future__ import annotations

from typing import Any

from fittrack.core.constants import (
    AGE_BRACKETS,
    BIOLOGICAL_SEX_TO_CODE,
    FITNESS_LEVEL_TO_CODE,
)
from fittrack.services.tiers import compute_tier_code, validate_tier_code


class ProfileError(Exception):
    """Domain error for profile operations."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# Fields required for a profile to be considered "complete"
REQUIRED_PROFILE_FIELDS = (
    "display_name",
    "date_of_birth",
    "state_of_residence",
    "biological_sex",
    "age_bracket",
    "fitness_level",
)

# Fields that affect tier code
TIER_FIELDS = ("biological_sex", "age_bracket", "fitness_level")


class ProfileService:
    """Service layer for profile operations."""

    def __init__(self, profile_repo: Any, user_repo: Any | None = None) -> None:
        self.profile_repo = profile_repo
        self.user_repo = user_repo

    # ── Read ────────────────────────────────────────────────────────

    def get_profile(self, profile_id: str) -> dict[str, Any]:
        """Get a profile by ID."""
        profile = self.profile_repo.find_by_id(profile_id)
        if profile is None:
            raise ProfileError("Profile not found", status_code=404)
        return profile

    def get_profile_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        """Get a profile by user_id. Returns None if not found."""
        return self.profile_repo.find_by_user_id(user_id)

    def list_profiles(
        self,
        page: int = 1,
        limit: int = 20,
        tier_code: str | None = None,
    ) -> dict[str, Any]:
        """List profiles with optional tier_code filter and pagination."""
        filters: dict[str, Any] = {}
        if tier_code:
            if not validate_tier_code(tier_code):
                raise ProfileError(f"Invalid tier code: {tier_code!r}")
            filters["tier_code"] = tier_code

        total = self.profile_repo.count(filters=filters)
        offset = (page - 1) * limit
        items = self.profile_repo.find_all(
            limit=limit, offset=offset, filters=filters,
        )
        total_pages = max(1, (total + limit - 1) // limit)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }

    # ── Write ───────────────────────────────────────────────────────

    def create_profile(
        self,
        user_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a profile for a user with computed tier code.

        Validates that the user doesn't already have a profile.
        """
        existing = self.profile_repo.find_by_user_id(user_id)
        if existing:
            raise ProfileError(
                "User already has a profile", status_code=409,
            )

        # Validate tier-relevant fields
        self._validate_tier_fields(data)

        tier_code = compute_tier_code(
            biological_sex=data["biological_sex"],
            age_bracket=data["age_bracket"],
            fitness_level=data["fitness_level"],
        )
        data["tier_code"] = tier_code
        data["user_id"] = user_id

        new_id = self.profile_repo.create(data=data)
        return {"profile_id": new_id, **data}

    def update_profile(
        self,
        profile_id: str,
        data: dict[str, Any],
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Update a profile.  Recomputes tier code if any tier field changes.

        If *user_id* is provided, verifies profle ownership.
        """
        if not data:
            raise ProfileError("No fields to update")

        # Ownership check
        if user_id:
            profile = self.profile_repo.find_by_id(profile_id)
            if profile is None:
                raise ProfileError("Profile not found", status_code=404)
            if profile.get("user_id") != user_id:
                raise ProfileError(
                    "Cannot update another user's profile",
                    status_code=403,
                )

        # Check if any tier field is changing
        tier_field_present = any(f in data for f in TIER_FIELDS)
        if tier_field_present:
            # Need all three to recompute — merge with existing if needed
            existing = self.profile_repo.find_by_id(profile_id)
            if existing is None:
                raise ProfileError("Profile not found", status_code=404)

            merged = {
                "biological_sex": data.get(
                    "biological_sex", existing.get("biological_sex"),
                ),
                "age_bracket": data.get(
                    "age_bracket", existing.get("age_bracket"),
                ),
                "fitness_level": data.get(
                    "fitness_level", existing.get("fitness_level"),
                ),
            }

            # Only recompute if we have all three values
            if all(merged.values()):
                data["tier_code"] = compute_tier_code(
                    biological_sex=merged["biological_sex"],
                    age_bracket=merged["age_bracket"],
                    fitness_level=merged["fitness_level"],
                )

        affected = self.profile_repo.update(profile_id, data=data)
        if affected == 0:
            raise ProfileError("Profile not found", status_code=404)

        return {"profile_id": profile_id, "updated": True}

    # ── Profile Completion ──────────────────────────────────────────

    def is_profile_complete(self, profile: dict[str, Any]) -> bool:
        """Check whether a profile has all required fields filled in."""
        for field in REQUIRED_PROFILE_FIELDS:
            value = profile.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                return False
        return True

    def check_profile_complete_for_user(self, user_id: str) -> bool:
        """Check whether the user has a complete profile."""
        profile = self.profile_repo.find_by_user_id(user_id)
        if profile is None:
            return False
        return self.is_profile_complete(profile)

    def get_user_with_profile(self, user_id: str) -> dict[str, Any]:
        """Get user data merged with their profile, if it exists."""
        if self.user_repo is None:
            raise ProfileError("User repository not configured")

        user = self.user_repo.find_by_id(user_id)
        if user is None:
            raise ProfileError("User not found", status_code=404)

        # Remove sensitive fields
        user.pop("password_hash", None)
        user.pop("failed_login_attempts", None)
        user.pop("locked_until", None)

        profile = self.profile_repo.find_by_user_id(user_id)
        result = {**user, "profile": profile}
        result["profile_complete"] = (
            self.is_profile_complete(profile) if profile else False
        )
        return result

    def get_public_profile(self, user_id: str) -> dict[str, Any]:
        """Get a public view of a user's profile (display name, tier, rank)."""
        profile = self.profile_repo.find_by_user_id(user_id)
        if profile is None:
            raise ProfileError("Profile not found", status_code=404)

        # Only expose public fields
        return {
            "user_id": user_id,
            "display_name": profile.get("display_name", ""),
            "tier_code": profile.get("tier_code", ""),
            "fitness_level": profile.get("fitness_level", ""),
            "age_bracket": profile.get("age_bracket", ""),
        }

    # ── Helpers ─────────────────────────────────────────────────────

    @staticmethod
    def _validate_tier_fields(data: dict[str, Any]) -> None:
        """Validate that tier-relevant fields have valid values."""
        sex = data.get("biological_sex")
        if sex and sex not in BIOLOGICAL_SEX_TO_CODE:
            msg = f"Invalid biological_sex: {sex!r}"
            raise ProfileError(msg)

        age = data.get("age_bracket")
        if age and age not in AGE_BRACKETS:
            msg = f"Invalid age_bracket: {age!r}"
            raise ProfileError(msg)

        fl = data.get("fitness_level")
        if fl and fl not in FITNESS_LEVEL_TO_CODE:
            msg = f"Invalid fitness_level: {fl!r}"
            raise ProfileError(msg)
