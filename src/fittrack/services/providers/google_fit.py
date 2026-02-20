"""Google Fit provider client.

Handles OAuth flow and activity fetching from the Google Fit REST API.
In MVP this uses simulated responses when actual API credentials are
not configured (the OAuth initiation/callback stubs are functional).
"""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from datetime import UTC, datetime, timedelta
from typing import Any

from fittrack.services.providers.base import (
    BaseProvider,
    ProviderError,
    RawActivity,
    TokenInfo,
)

logger = logging.getLogger(__name__)

# Google Fit API endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_FITNESS_BASE = "https://www.googleapis.com/fitness/v1/users/me"

GOOGLE_FIT_SCOPES = [
    "https://www.googleapis.com/auth/fitness.activity.read",
    "https://www.googleapis.com/auth/fitness.body.read",
    "https://www.googleapis.com/auth/fitness.location.read",
]


class GoogleFitProvider(BaseProvider):
    """Google Fit REST API provider.

    Requires ``GOOGLE_CLIENT_ID`` and ``GOOGLE_CLIENT_SECRET`` env vars
    for real OAuth.  Without them the client works in *stub mode* —
    ``exchange_code`` and ``fetch_activities`` return simulated data
    so the rest of the pipeline can be tested end-to-end.
    """

    provider_name = "google_fit"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self._stub_mode = not (self.client_id and self.client_secret)
        if self._stub_mode:
            logger.info("GoogleFitProvider running in STUB mode (no credentials)")

    # ── OAuth ───────────────────────────────────────────────────────

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GOOGLE_FIT_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> TokenInfo:
        if self._stub_mode:
            return TokenInfo(
                access_token=f"gfit_stub_access_{code[:8]}",
                refresh_token=f"gfit_stub_refresh_{code[:8]}",
                token_expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
                scopes=GOOGLE_FIT_SCOPES,
            )
        # Real implementation would POST to GOOGLE_TOKEN_URL
        raise ProviderError("google_fit", "Real OAuth not implemented in MVP")

    def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        if self._stub_mode:
            return TokenInfo(
                access_token=f"gfit_stub_refreshed_{refresh_token[:8]}",
                refresh_token=refresh_token,
                token_expires_at=datetime.now(tz=UTC) + timedelta(hours=1),
                scopes=GOOGLE_FIT_SCOPES,
            )
        raise ProviderError("google_fit", "Real token refresh not implemented in MVP")

    def revoke_token(self, token: str) -> bool:
        if self._stub_mode:
            logger.info("Stub: revoking Google token %s…", token[:8])
            return True
        raise ProviderError("google_fit", "Real token revocation not implemented in MVP")

    # ── Activity fetching ───────────────────────────────────────────

    def fetch_activities(
        self,
        access_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RawActivity]:
        """Fetch fitness activities from Google Fit.

        In stub mode returns deterministic simulated data based on the
        access token so tests are reproducible.
        """
        if self._stub_mode:
            return self._generate_stub_activities(access_token, start_time, end_time)
        raise ProviderError("google_fit", "Real API fetch not implemented in MVP")

    # ── Stub helpers ────────────────────────────────────────────────

    def _generate_stub_activities(
        self,
        access_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RawActivity]:
        """Generate deterministic simulated activities for testing."""
        activities: list[RawActivity] = []
        seed = int(hashlib.md5(access_token.encode()).hexdigest()[:8], 16)  # noqa: S324

        current = start_time
        day_num = 0
        while current < end_time:
            day_seed = seed + day_num
            # Steps activity
            step_count = 5000 + (day_seed % 15000)
            activities.append(
                RawActivity(
                    external_id=f"gfit_steps_{current.strftime('%Y%m%d')}_{day_seed:x}",
                    provider="google_fit",
                    activity_type="steps",
                    start_time=current.replace(hour=0, minute=0, second=0),
                    end_time=current.replace(hour=23, minute=59, second=59),
                    metrics={"step_count": step_count},
                    source_device="Google Pixel",
                )
            )

            # Workout if day_seed is even
            if day_seed % 2 == 0:
                duration = 20 + (day_seed % 40)
                intensities = ["light", "moderate", "vigorous"]
                intensity = intensities[day_seed % 3]
                activities.append(
                    RawActivity(
                        external_id=f"gfit_workout_{current.strftime('%Y%m%d')}_{day_seed:x}",
                        provider="google_fit",
                        activity_type="workout",
                        start_time=current.replace(hour=7, minute=0),
                        end_time=current.replace(hour=7, minute=duration),
                        duration_minutes=duration,
                        intensity=intensity,
                        metrics={
                            "calories_burned": duration * 8,
                            "workout_type": "running",
                        },
                        source_device="Google Pixel",
                    )
                )

            # Active minutes
            active_mins = 15 + (day_seed % 45)
            intensity_am = intensities[day_seed % 3] if day_seed % 2 == 0 else "moderate"
            activities.append(
                RawActivity(
                    external_id=f"gfit_active_{current.strftime('%Y%m%d')}_{day_seed:x}",
                    provider="google_fit",
                    activity_type="active_minutes",
                    start_time=current.replace(hour=6, minute=0),
                    end_time=current.replace(hour=22, minute=0),
                    duration_minutes=active_mins,
                    intensity=intensity_am,
                    metrics={"active_minutes": active_mins},
                    source_device="Google Pixel",
                )
            )

            current += timedelta(days=1)
            day_num += 1

        return activities

    @staticmethod
    def _parse_real_activities(_data: dict[str, Any]) -> list[RawActivity]:
        """Parse real Google Fit API response into RawActivity list.

        Placeholder for production implementation.
        """
        return []  # pragma: no cover
