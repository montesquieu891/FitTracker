"""Unit tests for Pydantic schemas — TDD: written BEFORE implementation is verified."""

from __future__ import annotations

from datetime import date, datetime

import pytest


class TestUserSchemas:
    """Test User Pydantic schemas."""

    def test_user_create_valid(self) -> None:
        from fittrack.api.schemas.users import UserCreate

        user = UserCreate(email="test@example.com", password_hash="hashed_pw_123")
        assert user.email == "test@example.com"
        assert user.role == "user"
        assert user.status == "pending"

    def test_user_create_invalid_email(self) -> None:
        from fittrack.api.schemas.users import UserCreate

        with pytest.raises(ValueError):
            UserCreate(email="not-an-email", password_hash="hash")

    def test_user_create_invalid_role(self) -> None:
        from fittrack.api.schemas.users import UserCreate

        with pytest.raises(ValueError):
            UserCreate(email="test@example.com", password_hash="hash", role="superadmin")

    def test_user_create_invalid_status(self) -> None:
        from fittrack.api.schemas.users import UserCreate

        with pytest.raises(ValueError):
            UserCreate(email="test@example.com", password_hash="hash", status="deleted")

    def test_user_update_partial(self) -> None:
        from fittrack.api.schemas.users import UserUpdate

        update = UserUpdate(status="active")
        assert update.status == "active"
        assert update.email is None
        assert update.role is None

    def test_user_response_from_dict(self) -> None:
        from fittrack.api.schemas.users import UserResponse

        data = {
            "user_id": "abc123",
            "email": "test@example.com",
            "status": "active",
            "role": "user",
            "point_balance": 500,
        }
        resp = UserResponse(**data)
        assert resp.user_id == "abc123"
        assert resp.point_balance == 500


class TestProfileSchemas:
    """Test Profile Pydantic schemas."""

    def test_profile_create_valid(self) -> None:
        from fittrack.api.schemas.profiles import ProfileCreate

        profile = ProfileCreate(
            user_id="user123",
            display_name="TestUser",
            date_of_birth=date(1990, 5, 15),
            state_of_residence="TX",
            biological_sex="male",
            age_bracket="30-39",
            fitness_level="intermediate",
        )
        assert profile.display_name == "TestUser"
        assert profile.biological_sex == "male"

    def test_profile_create_invalid_sex(self) -> None:
        from fittrack.api.schemas.profiles import ProfileCreate

        with pytest.raises(ValueError):
            ProfileCreate(
                user_id="user123",
                display_name="Test",
                date_of_birth=date(1990, 5, 15),
                state_of_residence="TX",
                biological_sex="other",
                age_bracket="30-39",
                fitness_level="intermediate",
            )

    def test_profile_create_invalid_age_bracket(self) -> None:
        from fittrack.api.schemas.profiles import ProfileCreate

        with pytest.raises(ValueError):
            ProfileCreate(
                user_id="user123",
                display_name="Test",
                date_of_birth=date(1990, 5, 15),
                state_of_residence="TX",
                biological_sex="male",
                age_bracket="25-35",  # invalid
                fitness_level="beginner",
            )

    def test_profile_create_invalid_fitness_level(self) -> None:
        from fittrack.api.schemas.profiles import ProfileCreate

        with pytest.raises(ValueError):
            ProfileCreate(
                user_id="user123",
                display_name="Test",
                date_of_birth=date(1990, 5, 15),
                state_of_residence="TX",
                biological_sex="female",
                age_bracket="40-49",
                fitness_level="elite",  # invalid
            )

    def test_profile_update_partial(self) -> None:
        from fittrack.api.schemas.profiles import ProfileUpdate

        update = ProfileUpdate(fitness_level="advanced")
        assert update.fitness_level == "advanced"
        assert update.display_name is None


class TestActivitySchemas:
    """Test Activity Pydantic schemas."""

    def test_activity_create_valid(self) -> None:
        from fittrack.api.schemas.activities import ActivityCreate

        act = ActivityCreate(
            user_id="user123",
            activity_type="workout",
            start_time=datetime(2026, 1, 15, 7, 0, 0),
            end_time=datetime(2026, 1, 15, 7, 45, 0),
            duration_minutes=45,
            intensity="vigorous",
            metrics={"calories": 450, "heart_rate_avg": 145},
            points_earned=185,
        )
        assert act.activity_type == "workout"
        assert act.intensity == "vigorous"

    def test_activity_create_invalid_type(self) -> None:
        from fittrack.api.schemas.activities import ActivityCreate

        with pytest.raises(ValueError):
            ActivityCreate(
                user_id="user123",
                activity_type="swimming",  # invalid
                start_time=datetime.now(),
            )

    def test_activity_create_invalid_intensity(self) -> None:
        from fittrack.api.schemas.activities import ActivityCreate

        with pytest.raises(ValueError):
            ActivityCreate(
                user_id="user123",
                activity_type="workout",
                start_time=datetime.now(),
                intensity="extreme",  # invalid
            )


class TestDrawingSchemas:
    """Test Drawing Pydantic schemas."""

    def test_drawing_create_valid(self) -> None:
        from fittrack.api.schemas.drawings import DrawingCreate

        d = DrawingCreate(
            drawing_type="daily",
            name="Daily Drawing - Jan 15",
            ticket_cost_points=100,
            drawing_time=datetime(2026, 1, 15, 21, 0, 0),
            ticket_sales_close=datetime(2026, 1, 15, 20, 55, 0),
        )
        assert d.drawing_type == "daily"
        assert d.status == "draft"

    def test_drawing_create_invalid_type(self) -> None:
        from fittrack.api.schemas.drawings import DrawingCreate

        with pytest.raises(ValueError):
            DrawingCreate(
                drawing_type="hourly",  # invalid
                name="Test",
                ticket_cost_points=100,
                drawing_time=datetime.now(),
                ticket_sales_close=datetime.now(),
            )

    def test_drawing_update_partial(self) -> None:
        from fittrack.api.schemas.drawings import DrawingUpdate

        update = DrawingUpdate(status="open")
        assert update.status == "open"
        assert update.name is None


class TestTicketSchemas:
    """Test Ticket schemas."""

    def test_ticket_create(self) -> None:
        from fittrack.api.schemas.tickets import TicketCreate

        t = TicketCreate(drawing_id="d123", user_id="u456")
        assert t.drawing_id == "d123"

    def test_ticket_response(self) -> None:
        from fittrack.api.schemas.tickets import TicketResponse

        resp = TicketResponse(
            ticket_id="t1",
            drawing_id="d1",
            user_id="u1",
            is_winner=True,
        )
        assert resp.is_winner is True


class TestSponsorSchemas:
    """Test Sponsor schemas."""

    def test_sponsor_create_valid(self) -> None:
        from fittrack.api.schemas.sponsors import SponsorCreate

        s = SponsorCreate(
            name="Amazon",
            contact_email="partner@amazon.com",
        )
        assert s.name == "Amazon"
        assert s.status == "active"

    def test_sponsor_create_invalid_status(self) -> None:
        from fittrack.api.schemas.sponsors import SponsorCreate

        with pytest.raises(ValueError):
            SponsorCreate(name="Test", status="deleted")

    def test_sponsor_update_partial(self) -> None:
        from fittrack.api.schemas.sponsors import SponsorUpdate

        update = SponsorUpdate(name="Updated Name")
        assert update.name == "Updated Name"
        assert update.status is None


class TestPrizeSchemas:
    """Test Prize schemas."""

    def test_prize_create_valid(self) -> None:
        from fittrack.api.schemas.prizes import PrizeCreate

        p = PrizeCreate(
            drawing_id="d1",
            rank=1,
            name="$50 Gift Card",
            value_usd=50.00,
            fulfillment_type="digital",
        )
        assert p.rank == 1
        assert p.quantity == 1

    def test_prize_create_invalid_rank(self) -> None:
        from fittrack.api.schemas.prizes import PrizeCreate

        with pytest.raises(ValueError):
            PrizeCreate(drawing_id="d1", rank=0, name="Test")


class TestFulfillmentSchemas:
    """Test Fulfillment schemas."""

    def test_fulfillment_create(self) -> None:
        from fittrack.api.schemas.fulfillments import FulfillmentCreate

        f = FulfillmentCreate(ticket_id="t1", prize_id="p1", user_id="u1")
        assert f.status == "pending"

    def test_fulfillment_update_valid(self) -> None:
        from fittrack.api.schemas.fulfillments import FulfillmentUpdate

        f = FulfillmentUpdate(status="shipped", tracking_number="1Z999AA10123456784")
        assert f.status == "shipped"

    def test_fulfillment_update_invalid_status(self) -> None:
        from fittrack.api.schemas.fulfillments import FulfillmentUpdate

        with pytest.raises(ValueError):
            FulfillmentUpdate(status="cancelled")  # not a valid fulfillment status


class TestTransactionSchemas:
    """Test Transaction schemas."""

    def test_transaction_create(self) -> None:
        from fittrack.api.schemas.transactions import TransactionCreate

        t = TransactionCreate(
            user_id="u1",
            transaction_type="earn",
            amount=100,
            balance_after=600,
            description="Steps earned",
        )
        assert t.amount == 100

    def test_transaction_create_invalid_type(self) -> None:
        from fittrack.api.schemas.transactions import TransactionCreate

        with pytest.raises(ValueError):
            TransactionCreate(
                user_id="u1",
                transaction_type="refund",  # invalid
                amount=100,
                balance_after=600,
            )


class TestConnectionSchemas:
    """Test Connection schemas."""

    def test_connection_create(self) -> None:
        from fittrack.api.schemas.connections import ConnectionCreate

        c = ConnectionCreate(user_id="u1", provider="fitbit")
        assert c.provider == "fitbit"
        assert c.is_primary is False

    def test_connection_create_invalid_provider(self) -> None:
        from fittrack.api.schemas.connections import ConnectionCreate

        with pytest.raises(ValueError):
            ConnectionCreate(user_id="u1", provider="garmin")  # invalid


class TestCommonSchemas:
    """Test common/shared schemas."""

    def test_pagination_meta(self) -> None:
        from fittrack.api.schemas.common import PaginationMeta

        p = PaginationMeta(page=1, limit=20, total_items=100, total_pages=5)
        assert p.total_pages == 5

    def test_error_response(self) -> None:
        from fittrack.api.schemas.common import ErrorResponse

        e = ErrorResponse(title="Not Found", status=404, detail="Resource not found")
        assert e.status == 404

    def test_health_response(self) -> None:
        from fittrack.api.schemas.common import HealthResponse

        h = HealthResponse(status="ok", environment="testing")
        assert h.status == "ok"
