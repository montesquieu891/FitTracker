"""Tests for fitness tracker providers — Google Fit and Fitbit."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fittrack.services.providers.base import (
    BaseProvider,
    ProviderError,
    RawActivity,
    TokenInfo,
)
from fittrack.services.providers.fitbit import FitbitProvider
from fittrack.services.providers.google_fit import GoogleFitProvider

# ── BaseProvider ────────────────────────────────────────────────────


class TestBaseProvider:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            BaseProvider()

    def test_raw_activity_creation(self):
        raw = RawActivity(
            external_id="ext1",
            provider="test",
            activity_type="steps",
            start_time=datetime(2026, 1, 15, 8, 0, tzinfo=UTC),
            metrics={"step_count": 5000},
        )
        assert raw.external_id == "ext1"
        assert raw.activity_type == "steps"
        assert raw.metrics["step_count"] == 5000

    def test_token_info_creation(self):
        token = TokenInfo(
            access_token="access_123",
            refresh_token="refresh_456",
            token_expires_at=datetime(2026, 1, 16, 0, 0, tzinfo=UTC),
        )
        assert token.access_token == "access_123"
        assert token.refresh_token == "refresh_456"

    def test_provider_error(self):
        err = ProviderError("google_fit", "Connection failed", retriable=True)
        assert err.provider == "google_fit"
        assert err.detail == "Connection failed"
        assert err.retriable is True
        assert "google_fit" in str(err)

    def test_validate_token_default(self):
        """Default validate_token returns True."""

        class DummyProvider(BaseProvider):
            provider_name = "dummy"

            def get_authorization_url(self, state, redirect_uri):
                return ""

            def exchange_code(self, code, redirect_uri):
                return TokenInfo(access_token="")

            def refresh_access_token(self, refresh_token):
                return TokenInfo(access_token="")

            def revoke_token(self, token):
                return True

            def fetch_activities(self, access_token, start_time, end_time):
                return []

        p = DummyProvider()
        assert p.validate_token("any") is True


# ── GoogleFitProvider ───────────────────────────────────────────────


class TestGoogleFitProvider:
    def test_stub_mode_by_default(self):
        provider = GoogleFitProvider()
        assert provider._stub_mode is True
        assert provider.provider_name == "google_fit"

    def test_real_mode_when_credentials_provided(self):
        provider = GoogleFitProvider(client_id="id", client_secret="secret")
        assert provider._stub_mode is False

    def test_get_authorization_url(self):
        provider = GoogleFitProvider(client_id="test_id", client_secret="secret")
        url = provider.get_authorization_url("state_123", "http://localhost/callback")
        assert "accounts.google.com" in url
        assert "test_id" in url
        assert "state_123" in url

    def test_stub_exchange_code(self):
        provider = GoogleFitProvider()
        token = provider.exchange_code("auth_code_123", "http://localhost/callback")
        assert token.access_token.startswith("gfit_stub_access_")
        assert token.refresh_token is not None
        assert token.token_expires_at is not None
        assert token.token_expires_at > datetime.now(tz=UTC)

    def test_stub_refresh_token(self):
        provider = GoogleFitProvider()
        token = provider.refresh_access_token("old_refresh_token")
        assert token.access_token.startswith("gfit_stub_refreshed_")
        assert token.refresh_token == "old_refresh_token"

    def test_stub_revoke_token(self):
        provider = GoogleFitProvider()
        assert provider.revoke_token("some_token") is True

    def test_stub_fetch_activities(self):
        provider = GoogleFitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        activities = provider.fetch_activities("stub_token", start, end)
        assert len(activities) >= 2  # At least steps + active_minutes

        # Verify all are RawActivity instances
        for act in activities:
            assert isinstance(act, RawActivity)
            assert act.provider == "google_fit"

    def test_stub_activities_deterministic(self):
        """Same token produces same activities."""
        provider = GoogleFitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        a1 = provider.fetch_activities("token_A", start, end)
        a2 = provider.fetch_activities("token_A", start, end)
        assert len(a1) == len(a2)
        assert a1[0].external_id == a2[0].external_id

    def test_stub_activities_vary_by_token(self):
        provider = GoogleFitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        a1 = provider.fetch_activities("token_A", start, end)
        a2 = provider.fetch_activities("token_B", start, end)
        # Different tokens produce different external IDs
        assert a1[0].external_id != a2[0].external_id

    def test_stub_multi_day(self):
        provider = GoogleFitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 18, 0, 0, tzinfo=UTC)  # 3 days
        activities = provider.fetch_activities("token", start, end)
        # At least 3 step activities (one per day)
        steps = [a for a in activities if a.activity_type == "steps"]
        assert len(steps) == 3

    def test_real_mode_raises(self):
        provider = GoogleFitProvider(client_id="real", client_secret="secret")
        with pytest.raises(ProviderError, match="not implemented"):
            provider.exchange_code("code", "redirect")

    def test_real_mode_fetch_raises(self):
        provider = GoogleFitProvider(client_id="real", client_secret="secret")
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        with pytest.raises(ProviderError, match="not implemented"):
            provider.fetch_activities("token", start, end)


# ── FitbitProvider ──────────────────────────────────────────────────


class TestFitbitProvider:
    def test_stub_mode_by_default(self):
        provider = FitbitProvider()
        assert provider._stub_mode is True
        assert provider.provider_name == "fitbit"

    def test_get_authorization_url(self):
        provider = FitbitProvider(client_id="fb_id", client_secret="secret")
        url = provider.get_authorization_url("state_abc", "http://localhost/cb")
        assert "fitbit.com" in url
        assert "fb_id" in url

    def test_stub_exchange_code(self):
        provider = FitbitProvider()
        token = provider.exchange_code("fb_code", "redirect")
        assert token.access_token.startswith("fitbit_stub_access_")
        assert token.token_expires_at > datetime.now(tz=UTC)

    def test_stub_refresh_token(self):
        provider = FitbitProvider()
        token = provider.refresh_access_token("fb_refresh")
        assert token.access_token.startswith("fitbit_stub_refreshed_")

    def test_stub_revoke(self):
        provider = FitbitProvider()
        assert provider.revoke_token("tok") is True

    def test_stub_fetch_activities(self):
        provider = FitbitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        activities = provider.fetch_activities("stub_token", start, end)
        assert len(activities) >= 2
        for act in activities:
            assert isinstance(act, RawActivity)
            assert act.provider == "fitbit"

    def test_fitbit_different_step_range(self):
        """Fitbit starts at 4000+ steps vs Google's 5000+."""
        provider = FitbitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        activities = provider.fetch_activities("test", start, end)
        steps_acts = [a for a in activities if a.activity_type == "steps"]
        for s in steps_acts:
            assert s.metrics.get("step_count", 0) >= 4000

    def test_fitbit_device_name(self):
        provider = FitbitProvider()
        start = datetime(2026, 1, 15, 0, 0, tzinfo=UTC)
        end = datetime(2026, 1, 16, 0, 0, tzinfo=UTC)
        activities = provider.fetch_activities("test", start, end)
        for a in activities:
            assert a.source_device == "Fitbit Charge 6"

    def test_real_mode_raises(self):
        provider = FitbitProvider(client_id="real", client_secret="secret")
        with pytest.raises(ProviderError, match="not implemented"):
            provider.exchange_code("code", "redirect")
