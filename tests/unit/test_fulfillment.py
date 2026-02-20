"""Tests for fulfillment service — state machine, timeouts, address validation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from fittrack.services.fulfillments import (
    ADDRESS_CONFIRM_FORFEIT_DAYS,
    ADDRESS_CONFIRM_WARNING_DAYS,
    FULFILLMENT_TRANSITIONS,
    FulfillmentError,
    FulfillmentService,
)

# ── Mock repositories ───────────────────────────────────────────────


class MockFulfillmentRepo:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self._store: dict[str, dict[str, Any]] = {}
        for item in items or []:
            fid = item.get("fulfillment_id", "")
            self._store[fid] = dict(item)

    def find_by_id(self, fid: str) -> dict[str, Any] | None:
        return self._store.get(fid)

    def find_all(
        self,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        items = list(self._store.values())
        if filters:
            for k, v in filters.items():
                items = [i for i in items if i.get(k) == v]
        return items[offset : offset + limit]

    def count(self, filters: dict[str, Any] | None = None) -> int:
        items = list(self._store.values())
        if filters:
            for k, v in filters.items():
                items = [i for i in items if i.get(k) == v]
        return len(items)

    def create(self, data: dict[str, Any], new_id: str) -> None:
        self._store[new_id] = {"fulfillment_id": new_id, **data}

    def update(self, fid: str, data: dict[str, Any]) -> int:
        if fid in self._store:
            self._store[fid].update(data)
            return 1
        return 0


def _make_fulfillment(status: str = "pending", **kwargs: Any) -> dict[str, Any]:
    return {
        "fulfillment_id": "f1",
        "ticket_id": "t1",
        "prize_id": "p1",
        "user_id": "u1",
        "drawing_id": "d1",
        "status": status,
        **kwargs,
    }


def _make_service(
    items: list[dict[str, Any]] | None = None,
) -> FulfillmentService:
    return FulfillmentService(fulfillment_repo=MockFulfillmentRepo(items))


# ── State machine transition tests ─────────────────────────────────


class TestStateTransitions:
    def test_pending_to_notified(self):
        svc = _make_service([_make_fulfillment("pending")])
        result = svc.notify_winner("f1")
        assert result["status"] == "winner_notified"
        assert result["notified_at"]

    def test_notified_to_confirmed(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        result = svc.confirm_address(
            "f1",
            {
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "zip_code": "90210",
            },
        )
        assert result["status"] == "address_confirmed"
        assert result["address_confirmed_at"]

    def test_notified_to_invalid(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        result = svc.mark_address_invalid("f1")
        assert result["status"] == "address_invalid"

    def test_invalid_to_confirmed_recovery(self):
        svc = _make_service([_make_fulfillment("address_invalid")])
        result = svc.confirm_address(
            "f1",
            {
                "street": "456 Oak Ave",
                "city": "Other City",
                "state": "NY",
                "zip_code": "10001",
            },
        )
        assert result["status"] == "address_confirmed"

    def test_confirmed_to_shipped(self):
        svc = _make_service([_make_fulfillment("address_confirmed")])
        result = svc.ship_prize("f1", carrier="UPS", tracking_number="1Z123")
        assert result["status"] == "shipped"
        assert result["shipped_at"]
        assert result["carrier"] == "UPS"
        assert result["tracking_number"] == "1Z123"

    def test_shipped_to_delivered(self):
        svc = _make_service([_make_fulfillment("shipped")])
        result = svc.mark_delivered("f1")
        assert result["status"] == "delivered"
        assert result["delivered_at"]

    def test_forfeit_from_pending(self):
        svc = _make_service([_make_fulfillment("pending")])
        result = svc.forfeit("f1", reason="Test")
        assert result["status"] == "forfeited"
        assert result["forfeit_at"]
        assert result["notes"] == "Test"

    def test_forfeit_from_notified(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        result = svc.forfeit("f1")
        assert result["status"] == "forfeited"

    def test_forfeit_from_confirmed(self):
        svc = _make_service([_make_fulfillment("address_confirmed")])
        result = svc.forfeit("f1")
        assert result["status"] == "forfeited"

    def test_forfeit_from_shipped(self):
        svc = _make_service([_make_fulfillment("shipped")])
        result = svc.forfeit("f1")
        assert result["status"] == "forfeited"


# ── Invalid transitions ────────────────────────────────────────────


class TestInvalidTransitions:
    def test_cannot_ship_from_pending(self):
        svc = _make_service([_make_fulfillment("pending")])
        with pytest.raises(FulfillmentError, match="Cannot transition"):
            svc.ship_prize("f1", carrier="UPS", tracking_number="1Z")

    def test_cannot_deliver_from_pending(self):
        svc = _make_service([_make_fulfillment("pending")])
        with pytest.raises(FulfillmentError, match="Cannot transition"):
            svc.mark_delivered("f1")

    def test_cannot_confirm_from_pending(self):
        svc = _make_service([_make_fulfillment("pending")])
        with pytest.raises(FulfillmentError, match="Cannot transition"):
            svc.confirm_address("f1", {"street": "x", "city": "x", "state": "x", "zip_code": "x"})

    def test_cannot_transition_from_delivered(self):
        svc = _make_service([_make_fulfillment("delivered")])
        with pytest.raises(FulfillmentError, match="Cannot transition"):
            svc.forfeit("f1")

    def test_cannot_transition_from_forfeited(self):
        svc = _make_service([_make_fulfillment("forfeited")])
        with pytest.raises(FulfillmentError, match="Cannot transition"):
            svc.notify_winner("f1")

    def test_not_found(self):
        svc = _make_service()
        with pytest.raises(FulfillmentError, match="not found"):
            svc.transition_status("nope", "winner_notified")

    def test_invalid_status_value(self):
        svc = _make_service([_make_fulfillment("pending")])
        with pytest.raises(FulfillmentError, match="Invalid status"):
            svc.transition_status("f1", "bogus")


# ── Address validation ──────────────────────────────────────────────


class TestAddressValidation:
    def test_missing_street(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        with pytest.raises(FulfillmentError, match="street"):
            svc.confirm_address("f1", {"city": "x", "state": "x", "zip_code": "x"})

    def test_missing_city(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        with pytest.raises(FulfillmentError, match="city"):
            svc.confirm_address("f1", {"street": "x", "state": "x", "zip_code": "x"})

    def test_missing_state(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        with pytest.raises(FulfillmentError, match="state"):
            svc.confirm_address("f1", {"street": "x", "city": "x", "zip_code": "x"})

    def test_missing_zip_code(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        with pytest.raises(FulfillmentError, match="zip_code"):
            svc.confirm_address("f1", {"street": "x", "city": "x", "state": "x"})

    def test_empty_address_rejected(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        with pytest.raises(FulfillmentError, match="required"):
            svc.confirm_address("f1", {})

    def test_address_stored_on_fulfillment(self):
        svc = _make_service([_make_fulfillment("winner_notified")])
        addr = {
            "street": "123 Main",
            "city": "Anytown",
            "state": "CA",
            "zip_code": "90210",
        }
        result = svc.confirm_address("f1", addr)
        assert result["shipping_address"] == addr


# ── Ship validation ─────────────────────────────────────────────────


class TestShipValidation:
    def test_empty_carrier_rejected(self):
        svc = _make_service([_make_fulfillment("address_confirmed")])
        with pytest.raises(FulfillmentError, match="Carrier"):
            svc.ship_prize("f1", carrier="", tracking_number="1Z")

    def test_empty_tracking_rejected(self):
        svc = _make_service([_make_fulfillment("address_confirmed")])
        with pytest.raises(FulfillmentError, match="Tracking number"):
            svc.ship_prize("f1", carrier="UPS", tracking_number="")


# ── Queries ─────────────────────────────────────────────────────────


class TestFulfillmentQueries:
    def test_get_fulfillment(self):
        f = _make_fulfillment("pending")
        svc = _make_service([f])
        result = svc.get_fulfillment("f1")
        assert result["fulfillment_id"] == "f1"

    def test_get_not_found(self):
        svc = _make_service()
        with pytest.raises(FulfillmentError, match="not found"):
            svc.get_fulfillment("nope")

    def test_list_fulfillments_all(self):
        items = [{**_make_fulfillment("pending"), "fulfillment_id": f"f{i}"} for i in range(5)]
        svc = _make_service(items)
        result = svc.list_fulfillments()
        assert result["pagination"]["total_items"] == 5

    def test_list_filter_by_status(self):
        items = [
            {**_make_fulfillment("pending"), "fulfillment_id": "f1"},
            {**_make_fulfillment("shipped"), "fulfillment_id": "f2"},
        ]
        svc = _make_service(items)
        result = svc.list_fulfillments(status="pending")
        assert result["pagination"]["total_items"] == 1

    def test_list_filter_by_user(self):
        items = [
            {**_make_fulfillment("pending"), "fulfillment_id": "f1", "user_id": "u1"},
            {**_make_fulfillment("pending"), "fulfillment_id": "f2", "user_id": "u2"},
        ]
        svc = _make_service(items)
        result = svc.list_fulfillments(user_id="u1")
        assert result["pagination"]["total_items"] == 1

    def test_list_pagination(self):
        items = [{**_make_fulfillment("pending"), "fulfillment_id": f"f{i}"} for i in range(10)]
        svc = _make_service(items)
        result = svc.list_fulfillments(page=2, limit=3)
        assert len(result["items"]) == 3
        assert result["pagination"]["total_pages"] == 4


# ── Timeout checks ──────────────────────────────────────────────────


class TestTimeoutChecks:
    def test_warning_after_7_days(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        f = _make_fulfillment("winner_notified", notified_at=notified.isoformat())
        svc = _make_service([f])
        now = notified + timedelta(days=ADDRESS_CONFIRM_WARNING_DAYS)
        assert svc.check_confirmation_warning("f1", now) is True

    def test_no_warning_before_7_days(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        f = _make_fulfillment("winner_notified", notified_at=notified.isoformat())
        svc = _make_service([f])
        now = notified + timedelta(days=6)
        assert svc.check_confirmation_warning("f1", now) is False

    def test_warning_wrong_status(self):
        f = _make_fulfillment("pending")
        svc = _make_service([f])
        assert svc.check_confirmation_warning("f1") is False

    def test_warning_not_found(self):
        svc = _make_service()
        assert svc.check_confirmation_warning("nope") is False

    def test_forfeit_after_14_days(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        f = _make_fulfillment("winner_notified", notified_at=notified.isoformat())
        svc = _make_service([f])
        now = notified + timedelta(days=ADDRESS_CONFIRM_FORFEIT_DAYS)
        assert svc.check_forfeit_timeout("f1", now) is True

    def test_no_forfeit_before_14_days(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        f = _make_fulfillment("winner_notified", notified_at=notified.isoformat())
        svc = _make_service([f])
        now = notified + timedelta(days=13)
        assert svc.check_forfeit_timeout("f1", now) is False

    def test_no_forfeit_for_shipped(self):
        f = _make_fulfillment("shipped")
        svc = _make_service([f])
        assert svc.check_forfeit_timeout("f1") is False

    def test_no_forfeit_for_delivered(self):
        f = _make_fulfillment("delivered")
        svc = _make_service([f])
        assert svc.check_forfeit_timeout("f1") is False

    def test_no_forfeit_already_forfeited(self):
        f = _make_fulfillment("forfeited")
        svc = _make_service([f])
        assert svc.check_forfeit_timeout("f1") is False

    def test_no_forfeit_without_notification(self):
        f = _make_fulfillment("pending")
        svc = _make_service([f])
        assert svc.check_forfeit_timeout("f1") is False


# ── Process timeouts ────────────────────────────────────────────────


class TestProcessTimeouts:
    def test_batch_forfeit(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        items = [
            {
                **_make_fulfillment("winner_notified"),
                "fulfillment_id": f"f{i}",
                "notified_at": notified.isoformat(),
            }
            for i in range(3)
        ]
        svc = _make_service(items)
        now = notified + timedelta(days=15)
        result = svc.process_timeouts(now)
        assert result["forfeited"] == 3

    def test_batch_warning_no_forfeit(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        items = [
            {
                **_make_fulfillment("winner_notified"),
                "fulfillment_id": "f1",
                "notified_at": notified.isoformat(),
            }
        ]
        svc = _make_service(items)
        # Between 7 and 14 days — warning but not forfeit
        now = notified + timedelta(days=10)
        result = svc.process_timeouts(now)
        assert result["warnings_sent"] == 1
        assert result["forfeited"] == 0

    def test_batch_no_action_recent(self):
        notified = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
        items = [
            {
                **_make_fulfillment("winner_notified"),
                "fulfillment_id": "f1",
                "notified_at": notified.isoformat(),
            }
        ]
        svc = _make_service(items)
        now = notified + timedelta(days=3)
        result = svc.process_timeouts(now)
        assert result["warnings_sent"] == 0
        assert result["forfeited"] == 0


# ── Transitions map completeness ────────────────────────────────────


class TestTransitionsMap:
    def test_all_statuses_covered(self):
        from fittrack.core.constants import FULFILLMENT_STATUSES

        for s in FULFILLMENT_STATUSES:
            assert s in FULFILLMENT_TRANSITIONS

    def test_terminal_states_empty(self):
        assert FULFILLMENT_TRANSITIONS["delivered"] == []
        assert FULFILLMENT_TRANSITIONS["forfeited"] == []

    def test_constants_match(self):
        assert ADDRESS_CONFIRM_WARNING_DAYS == 7
        assert ADDRESS_CONFIRM_FORFEIT_DAYS == 14
