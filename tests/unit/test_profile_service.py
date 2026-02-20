"""Tests for the ProfileService business logic."""

from __future__ import annotations

from typing import Any

import pytest

from fittrack.services.profiles import (
    REQUIRED_PROFILE_FIELDS,
    ProfileError,
    ProfileService,
)

# ── Mock repos ──────────────────────────────────────────────────────


class FakeProfileRepo:
    """In-memory profile repository for service-level unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        self._next_id = 1

    def find_by_id(self, profile_id: str) -> dict[str, Any] | None:
        return self._store.get(profile_id)

    def find_by_user_id(self, user_id: str) -> dict[str, Any] | None:
        for p in self._store.values():
            if p.get("user_id") == user_id:
                return p
        return None

    def find_all(
        self,
        limit: int = 20,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        items = list(self._store.values())
        if filters:
            for key, val in filters.items():
                items = [i for i in items if i.get(key) == val]
        return items[offset : offset + limit]

    def count(self, filters: dict[str, Any] | None = None) -> int:
        if not filters:
            return len(self._store)
        items = list(self._store.values())
        for key, val in filters.items():
            items = [i for i in items if i.get(key) == val]
        return len(items)

    def create(self, data: dict[str, Any], new_id: str | None = None) -> str:
        pid = new_id or f"p{self._next_id}"
        self._next_id += 1
        record = {"profile_id": pid, **data}
        self._store[pid] = record
        return pid

    def update(self, profile_id: str, data: dict[str, Any]) -> int:
        if profile_id not in self._store:
            return 0
        self._store[profile_id].update(data)
        return 1


class FakeUserRepo:
    """In-memory user repository for service-level unit tests."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    def add(self, user_id: str, **extra: Any) -> dict[str, Any]:
        user = {
            "user_id": user_id,
            "email": f"{user_id}@example.com",
            "role": "user",
            "status": "active",
            "point_balance": 0,
            **extra,
        }
        self._store[user_id] = user
        return user

    def find_by_id(self, user_id: str) -> dict[str, Any] | None:
        return self._store.get(user_id)


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
def profile_repo() -> FakeProfileRepo:
    return FakeProfileRepo()


@pytest.fixture
def user_repo() -> FakeUserRepo:
    repo = FakeUserRepo()
    repo.add("u1")
    repo.add("u2")
    return repo


@pytest.fixture
def svc(profile_repo: FakeProfileRepo, user_repo: FakeUserRepo) -> ProfileService:
    return ProfileService(profile_repo=profile_repo, user_repo=user_repo)


def _complete_profile_data() -> dict[str, Any]:
    """Return all required fields for a complete profile."""
    return {
        "display_name": "Jane Doe",
        "date_of_birth": "1990-05-15",
        "state_of_residence": "CA",
        "biological_sex": "female",
        "age_bracket": "30-39",
        "fitness_level": "intermediate",
    }


# ── Create Profile ──────────────────────────────────────────────────


class TestCreateProfile:
    """Test ProfileService.create_profile()."""

    def test_create_sets_tier_code(self, svc: ProfileService) -> None:
        result = svc.create_profile("u1", _complete_profile_data())
        assert result["tier_code"] == "F-30-39-INT"
        assert "profile_id" in result

    def test_create_stores_user_id(self, svc: ProfileService) -> None:
        result = svc.create_profile("u1", _complete_profile_data())
        assert result["user_id"] == "u1"

    def test_create_duplicate_raises_409(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        with pytest.raises(ProfileError, match="already has a profile") as exc_info:
            svc.create_profile("u1", _complete_profile_data())
        assert exc_info.value.status_code == 409

    def test_create_male_beginner(self, svc: ProfileService) -> None:
        data = _complete_profile_data()
        data["biological_sex"] = "male"
        data["age_bracket"] = "18-29"
        data["fitness_level"] = "beginner"
        result = svc.create_profile("u1", data)
        assert result["tier_code"] == "M-18-29-BEG"

    def test_create_invalid_sex_raises(self, svc: ProfileService) -> None:
        data = _complete_profile_data()
        data["biological_sex"] = "other"
        with pytest.raises(ProfileError, match="biological_sex"):
            svc.create_profile("u1", data)

    def test_create_invalid_age_bracket_raises(self, svc: ProfileService) -> None:
        data = _complete_profile_data()
        data["age_bracket"] = "99-100"
        with pytest.raises(ProfileError, match="age_bracket"):
            svc.create_profile("u1", data)

    def test_create_invalid_fitness_level_raises(self, svc: ProfileService) -> None:
        data = _complete_profile_data()
        data["fitness_level"] = "elite"
        with pytest.raises(ProfileError, match="fitness_level"):
            svc.create_profile("u1", data)


# ── Update Profile ──────────────────────────────────────────────────


class TestUpdateProfile:
    """Test ProfileService.update_profile()."""

    def _seed(self, svc: ProfileService) -> str:
        result = svc.create_profile("u1", _complete_profile_data())
        return result["profile_id"]

    def test_update_display_name(self, svc: ProfileService) -> None:
        pid = self._seed(svc)
        result = svc.update_profile(pid, {"display_name": "New Name"})
        assert result["updated"] is True

    def test_update_recomputes_tier_on_sex_change(
        self, svc: ProfileService, profile_repo: FakeProfileRepo,
    ) -> None:
        pid = self._seed(svc)
        svc.update_profile(pid, {"biological_sex": "male"})
        updated = profile_repo.find_by_id(pid)
        assert updated is not None
        assert updated["tier_code"] == "M-30-39-INT"

    def test_update_recomputes_tier_on_age_change(
        self, svc: ProfileService, profile_repo: FakeProfileRepo,
    ) -> None:
        pid = self._seed(svc)
        svc.update_profile(pid, {"age_bracket": "40-49"})
        updated = profile_repo.find_by_id(pid)
        assert updated is not None
        assert updated["tier_code"] == "F-40-49-INT"

    def test_update_recomputes_tier_on_fitness_change(
        self, svc: ProfileService, profile_repo: FakeProfileRepo,
    ) -> None:
        pid = self._seed(svc)
        svc.update_profile(pid, {"fitness_level": "advanced"})
        updated = profile_repo.find_by_id(pid)
        assert updated is not None
        assert updated["tier_code"] == "F-30-39-ADV"

    def test_update_empty_data_raises(self, svc: ProfileService) -> None:
        pid = self._seed(svc)
        with pytest.raises(ProfileError, match="No fields"):
            svc.update_profile(pid, {})

    def test_update_nonexistent_raises_404(self, svc: ProfileService) -> None:
        with pytest.raises(ProfileError, match="not found") as exc_info:
            svc.update_profile("nonexistent", {"display_name": "X"})
        assert exc_info.value.status_code == 404

    def test_update_ownership_check_passes(self, svc: ProfileService) -> None:
        pid = self._seed(svc)
        result = svc.update_profile(pid, {"display_name": "OK"}, user_id="u1")
        assert result["updated"] is True

    def test_update_ownership_check_fails(self, svc: ProfileService) -> None:
        pid = self._seed(svc)
        with pytest.raises(ProfileError, match="another user") as exc_info:
            svc.update_profile(
                pid, {"display_name": "Hacked"}, user_id="u2",
            )
        assert exc_info.value.status_code == 403


# ── Profile Completion ──────────────────────────────────────────────


class TestProfileCompletion:
    """Test profile completeness checks."""

    def test_complete_profile(self, svc: ProfileService) -> None:
        profile = _complete_profile_data()
        assert svc.is_profile_complete(profile) is True

    @pytest.mark.parametrize("field", REQUIRED_PROFILE_FIELDS)
    def test_missing_field_is_incomplete(
        self, svc: ProfileService, field: str,
    ) -> None:
        profile = _complete_profile_data()
        del profile[field]
        assert svc.is_profile_complete(profile) is False

    @pytest.mark.parametrize("field", REQUIRED_PROFILE_FIELDS)
    def test_none_field_is_incomplete(
        self, svc: ProfileService, field: str,
    ) -> None:
        profile = _complete_profile_data()
        profile[field] = None
        assert svc.is_profile_complete(profile) is False

    def test_blank_string_is_incomplete(self, svc: ProfileService) -> None:
        profile = _complete_profile_data()
        profile["display_name"] = "   "
        assert svc.is_profile_complete(profile) is False

    def test_check_for_user_with_profile(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        assert svc.check_profile_complete_for_user("u1") is True

    def test_check_for_user_without_profile(self, svc: ProfileService) -> None:
        assert svc.check_profile_complete_for_user("u1") is False


# ── Get User With Profile ───────────────────────────────────────────


class TestGetUserWithProfile:
    """Test ProfileService.get_user_with_profile()."""

    def test_user_with_profile(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        result = svc.get_user_with_profile("u1")
        assert result["user_id"] == "u1"
        assert result["profile"] is not None
        assert result["profile_complete"] is True

    def test_user_without_profile(self, svc: ProfileService) -> None:
        result = svc.get_user_with_profile("u1")
        assert result["user_id"] == "u1"
        assert result["profile"] is None
        assert result["profile_complete"] is False

    def test_strips_sensitive_fields(self, svc: ProfileService) -> None:
        # Add sensitive fields to user repo
        svc.user_repo._store["u1"]["password_hash"] = "secret"
        svc.user_repo._store["u1"]["failed_login_attempts"] = 3
        result = svc.get_user_with_profile("u1")
        assert "password_hash" not in result
        assert "failed_login_attempts" not in result

    def test_nonexistent_user_raises_404(self, svc: ProfileService) -> None:
        with pytest.raises(ProfileError, match="not found") as exc_info:
            svc.get_user_with_profile("nonexistent")
        assert exc_info.value.status_code == 404

    def test_no_user_repo_raises(
        self, profile_repo: FakeProfileRepo,
    ) -> None:
        svc = ProfileService(profile_repo=profile_repo)
        with pytest.raises(ProfileError, match="not configured"):
            svc.get_user_with_profile("u1")


# ── Public Profile ──────────────────────────────────────────────────


class TestGetPublicProfile:
    """Test ProfileService.get_public_profile()."""

    def test_public_profile_fields(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        result = svc.get_public_profile("u1")
        assert set(result.keys()) == {
            "user_id", "display_name", "tier_code",
            "fitness_level", "age_bracket",
        }
        assert result["user_id"] == "u1"
        assert result["display_name"] == "Jane Doe"

    def test_public_profile_nonexistent_raises_404(
        self, svc: ProfileService,
    ) -> None:
        with pytest.raises(ProfileError, match="not found") as exc_info:
            svc.get_public_profile("nobody")
        assert exc_info.value.status_code == 404


# ── List Profiles ───────────────────────────────────────────────────


class TestListProfiles:
    """Test ProfileService.list_profiles()."""

    def test_empty_list(self, svc: ProfileService) -> None:
        result = svc.list_profiles()
        assert result["items"] == []
        assert result["pagination"]["total_items"] == 0

    def test_list_with_items(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        data2 = _complete_profile_data()
        data2["biological_sex"] = "male"
        data2["display_name"] = "John"
        svc.create_profile("u2", data2)
        result = svc.list_profiles()
        assert result["pagination"]["total_items"] == 2

    def test_list_filter_by_tier(self, svc: ProfileService) -> None:
        svc.create_profile("u1", _complete_profile_data())
        data2 = _complete_profile_data()
        data2["biological_sex"] = "male"
        data2["display_name"] = "John"
        svc.create_profile("u2", data2)
        result = svc.list_profiles(tier_code="F-30-39-INT")
        assert result["pagination"]["total_items"] == 1

    def test_list_invalid_tier_raises(self, svc: ProfileService) -> None:
        with pytest.raises(ProfileError, match="Invalid tier code"):
            svc.list_profiles(tier_code="INVALID")
