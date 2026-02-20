"""Tests for the tier engine — services/tiers.py and routes/tiers.py."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from fittrack.core.constants import (
    AGE_BRACKETS,
    ALL_TIER_CODES,
    BIOLOGICAL_SEX_TO_CODE,
    FITNESS_LEVEL_NAMES,
    FITNESS_LEVEL_TO_CODE,
    SEX_CATEGORY_NAMES,
)
from fittrack.services.tiers import (
    TierService,
    compute_tier_code,
    enumerate_tiers,
    get_tier_display_name,
    parse_tier_code,
    validate_tier_code,
)
from tests.conftest import MockCursor, set_mock_query_result

# ── Pure-function tests ─────────────────────────────────────────────


class TestComputeTierCode:
    """Test tier code computation from profile fields."""

    @pytest.mark.parametrize(
        ("sex", "age", "level", "expected"),
        [
            ("male", "18-29", "beginner", "M-18-29-BEG"),
            ("male", "30-39", "intermediate", "M-30-39-INT"),
            ("male", "40-49", "advanced", "M-40-49-ADV"),
            ("male", "50-59", "beginner", "M-50-59-BEG"),
            ("male", "60+", "intermediate", "M-60+-INT"),
            ("female", "18-29", "advanced", "F-18-29-ADV"),
            ("female", "30-39", "beginner", "F-30-39-BEG"),
            ("female", "40-49", "intermediate", "F-40-49-INT"),
            ("female", "50-59", "advanced", "F-50-59-ADV"),
            ("female", "60+", "beginner", "F-60+-BEG"),
        ],
    )
    def test_compute(
        self, sex: str, age: str, level: str, expected: str,
    ) -> None:
        assert compute_tier_code(sex, age, level) == expected

    def test_all_30_combos_produce_valid_codes(self) -> None:
        codes = set()
        for sex in BIOLOGICAL_SEX_TO_CODE:
            for age in AGE_BRACKETS:
                for level in FITNESS_LEVEL_TO_CODE:
                    code = compute_tier_code(sex, age, level)
                    assert code in ALL_TIER_CODES
                    codes.add(code)
        assert len(codes) == 30

    def test_invalid_sex_raises(self) -> None:
        with pytest.raises(ValueError, match="biological_sex"):
            compute_tier_code("other", "18-29", "beginner")

    def test_invalid_age_raises(self) -> None:
        with pytest.raises(ValueError, match="age_bracket"):
            compute_tier_code("male", "99-100", "beginner")

    def test_invalid_fitness_raises(self) -> None:
        with pytest.raises(ValueError, match="fitness_level"):
            compute_tier_code("male", "18-29", "elite")


class TestValidateTierCode:
    """Test tier code validation."""

    @pytest.mark.parametrize("code", ALL_TIER_CODES)
    def test_all_valid_codes(self, code: str) -> None:
        assert validate_tier_code(code) is True

    @pytest.mark.parametrize(
        "code",
        ["X-18-29-BEG", "M-99-99-BEG", "M-18-29-XYZ", "", "invalid"],
    )
    def test_invalid_codes(self, code: str) -> None:
        assert validate_tier_code(code) is False


class TestParseTierCode:
    """Test tier code parsing."""

    def test_parse_male_beginner(self) -> None:
        result = parse_tier_code("M-18-29-BEG")
        assert result == {
            "sex": "M",
            "age_bracket": "18-29",
            "fitness_level": "BEG",
        }

    def test_parse_female_advanced_60plus(self) -> None:
        result = parse_tier_code("F-60+-ADV")
        assert result == {
            "sex": "F",
            "age_bracket": "60+",
            "fitness_level": "ADV",
        }

    def test_parse_intermediate(self) -> None:
        result = parse_tier_code("M-40-49-INT")
        assert result == {
            "sex": "M",
            "age_bracket": "40-49",
            "fitness_level": "INT",
        }

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid tier code"):
            parse_tier_code("INVALID")


class TestGetTierDisplayName:
    """Test tier display-name generation."""

    def test_male_beginner(self) -> None:
        assert get_tier_display_name("M-18-29-BEG") == "Male · 18-29 · Beginner"

    def test_female_advanced(self) -> None:
        assert get_tier_display_name("F-40-49-ADV") == "Female · 40-49 · Advanced"

    def test_all_valid_codes_have_display_names(self) -> None:
        for code in ALL_TIER_CODES:
            name = get_tier_display_name(code)
            assert "·" in name
            assert len(name) > 5


class TestEnumerateTiers:
    """Test full tier enumeration."""

    def test_returns_30_tiers(self) -> None:
        tiers = enumerate_tiers()
        assert len(tiers) == 30

    def test_all_required_keys(self) -> None:
        keys = {
            "tier_code", "display_name", "sex", "sex_name",
            "age_bracket", "fitness_level", "fitness_level_name",
        }
        for tier in enumerate_tiers():
            assert keys.issubset(tier.keys())

    def test_codes_match_all_tier_codes(self) -> None:
        codes = {t["tier_code"] for t in enumerate_tiers()}
        assert codes == set(ALL_TIER_CODES)

    def test_display_names_include_descriptive_text(self) -> None:
        for tier in enumerate_tiers():
            # sex_name should be in display_name
            assert tier["sex_name"] in tier["display_name"]
            # fitness_level_name should be in display_name
            assert tier["fitness_level_name"] in tier["display_name"]

    def test_sex_names_are_valid(self) -> None:
        for tier in enumerate_tiers():
            assert tier["sex_name"] in SEX_CATEGORY_NAMES.values()

    def test_fitness_level_names_are_valid(self) -> None:
        for tier in enumerate_tiers():
            assert tier["fitness_level_name"] in FITNESS_LEVEL_NAMES.values()


# ── TierService tests (requires mock repo) ──────────────────────────


class MockProfileRepo:
    """Minimal mock for ProfileRepository.count()."""

    def __init__(self, count_value: int = 0) -> None:
        self._count = count_value

    def count(self, filters: dict[str, Any] | None = None) -> int:
        return self._count


class TestTierService:
    """Test TierService methods."""

    def test_get_tier_with_user_count_valid(self) -> None:
        svc = TierService(profile_repo=MockProfileRepo(count_value=42))
        result = svc.get_tier_with_user_count("M-18-29-BEG")
        assert result["tier_code"] == "M-18-29-BEG"
        assert result["user_count"] == 42
        assert result["display_name"] == "Male · 18-29 · Beginner"
        assert result["sex"] == "M"
        assert result["sex_name"] == "Male"
        assert result["fitness_level"] == "BEG"
        assert result["fitness_level_name"] == "Beginner"
        assert result["age_bracket"] == "18-29"

    def test_get_tier_with_user_count_invalid(self) -> None:
        svc = TierService(profile_repo=MockProfileRepo())
        with pytest.raises(ValueError, match="Invalid tier code"):
            svc.get_tier_with_user_count("INVALID")

    def test_list_all_tiers_with_counts(self) -> None:
        svc = TierService(profile_repo=MockProfileRepo(count_value=5))
        result = svc.list_all_tiers_with_counts()
        assert len(result) == 30
        for tier in result:
            assert tier["user_count"] == 5

    def test_list_all_tiers_keys(self) -> None:
        svc = TierService(profile_repo=MockProfileRepo())
        result = svc.list_all_tiers_with_counts()
        for tier in result:
            assert "user_count" in tier
            assert "tier_code" in tier
            assert "display_name" in tier


# ── Tier route tests ────────────────────────────────────────────────


class TestTierRoutes:
    """Test /api/v1/tiers endpoints."""

    def test_list_tiers_without_counts(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tiers")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30
        assert len(data["items"]) == 30
        # Without include_counts, no user_count key
        assert "user_count" not in data["items"][0]

    def test_list_tiers_with_counts(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        # Each tier queries count — mock returns 0
        set_mock_query_result(mock_cursor, ["cnt"], [(0,)])
        resp = client.get("/api/v1/tiers?include_counts=true")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 30
        assert "user_count" in data["items"][0]

    def test_get_tier_valid(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(7,)])
        resp = client.get("/api/v1/tiers/M-18-29-BEG")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier_code"] == "M-18-29-BEG"
        assert data["user_count"] == 7
        assert data["display_name"] == "Male · 18-29 · Beginner"

    def test_get_tier_invalid_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/tiers/INVALID")
        assert resp.status_code == 404

    def test_get_tier_female_advanced(
        self, client: TestClient, mock_cursor: MockCursor,
    ) -> None:
        set_mock_query_result(mock_cursor, ["cnt"], [(3,)])
        resp = client.get("/api/v1/tiers/F-40-49-ADV")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier_code"] == "F-40-49-ADV"
        assert data["display_name"] == "Female · 40-49 · Advanced"

    def test_tier_list_items_have_required_keys(
        self, client: TestClient,
    ) -> None:
        resp = client.get("/api/v1/tiers")
        data = resp.json()
        required = {
            "tier_code", "display_name", "sex", "sex_name",
            "age_bracket", "fitness_level", "fitness_level_name",
        }
        for item in data["items"]:
            assert required.issubset(item.keys())
