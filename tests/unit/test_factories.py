"""Unit tests for data factories — ensure factories produce valid data."""

from __future__ import annotations


class TestFactories:
    """Verify factory output conforms to Pydantic schemas."""

    def test_build_user(self) -> None:
        from tests.factories.data_factories import build_user
        user = build_user()
        assert "user_id" in user
        assert "@" in user["email"]
        assert user["role"] in ("user", "premium", "admin")

    def test_build_user_override(self) -> None:
        from tests.factories.data_factories import build_user
        user = build_user(email="custom@test.com", role="admin")
        assert user["email"] == "custom@test.com"
        assert user["role"] == "admin"

    def test_build_user_batch(self) -> None:
        from tests.factories.data_factories import build_user_batch
        users = build_user_batch(5)
        assert len(users) == 5
        emails = [u["email"] for u in users]
        assert len(set(emails)) == 5  # all unique

    def test_build_profile(self) -> None:
        from tests.factories.data_factories import build_profile
        profile = build_profile()
        assert profile["biological_sex"] in ("male", "female")
        assert profile["age_bracket"] in ("18-29", "30-39", "40-49", "50-59", "60+")
        assert "-" in profile["tier_code"]

    def test_build_activity(self) -> None:
        from tests.factories.data_factories import build_activity
        activity = build_activity(user_id="u123")
        assert activity["user_id"] == "u123"
        assert activity["activity_type"] in ("steps", "workout", "active_minutes")

    def test_build_connection(self) -> None:
        from tests.factories.data_factories import build_connection
        conn = build_connection()
        assert conn["provider"] in ("google_fit", "fitbit")

    def test_build_transaction(self) -> None:
        from tests.factories.data_factories import build_transaction
        txn = build_transaction()
        assert txn["transaction_type"] in ("earn", "spend", "adjust")
        assert txn["amount"] > 0

    def test_build_drawing(self) -> None:
        from tests.factories.data_factories import build_drawing
        drawing = build_drawing()
        assert drawing["drawing_type"] in ("daily", "weekly", "monthly", "annual")
        assert drawing["status"] == "draft"

    def test_build_ticket(self) -> None:
        from tests.factories.data_factories import build_ticket
        ticket = build_ticket(drawing_id="d1", user_id="u1")
        assert ticket["drawing_id"] == "d1"
        assert ticket["user_id"] == "u1"
        assert ticket["is_winner"] is False

    def test_build_prize(self) -> None:
        from tests.factories.data_factories import build_prize
        prize = build_prize()
        assert prize["rank"] >= 1
        assert prize["value_usd"] > 0

    def test_build_sponsor(self) -> None:
        from tests.factories.data_factories import build_sponsor
        sponsor = build_sponsor()
        assert sponsor["status"] == "active"
        assert len(sponsor["name"]) > 0

    def test_build_fulfillment(self) -> None:
        from tests.factories.data_factories import build_fulfillment
        ful = build_fulfillment()
        assert ful["status"] == "pending"
        assert "street" in ful["shipping_address"]

    def test_state_eligibility_in_profiles(self) -> None:
        """Profiles should only use eligible states."""
        from fittrack.core.constants import EXCLUDED_STATES
        from tests.factories.data_factories import build_profile
        for _ in range(50):
            profile = build_profile()
            assert profile["state_of_residence"] not in EXCLUDED_STATES
