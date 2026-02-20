"""Fitbit provider client.

Handles OAuth 2.0 flow and activity fetching from the Fitbit Web API.
Like Google Fit, operates in stub mode when credentials are not provided.
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

# Fitbit API endpoints
FITBIT_AUTH_URL = "https://www.fitbit.com/oauth2/authorize"
FITBIT_TOKEN_URL = "https://api.fitbit.com/oauth2/token"
FITBIT_REVOKE_URL = "https://api.fitbit.com/oauth2/revoke"
FITBIT_API_BASE = "https://api.fitbit.com/1/user/-"

FITBIT_SCOPES = [
    "activity",
    "heartrate",
    "profile",
    "settings",
]


class FitbitProvider(BaseProvider):
    """Fitbit Web API provider.

    Requires ``FITBIT_CLIENT_ID`` and ``FITBIT_CLIENT_SECRET`` env vars
    for real OAuth.  Without them the client works in *stub mode*.
    """

    provider_name = "fitbit"

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        self.client_id = client_id or ""
        self.client_secret = client_secret or ""
        self._stub_mode = not (self.client_id and self.client_secret)
        if self._stub_mode:
            logger.info("FitbitProvider running in STUB mode (no credentials)")

    # ── OAuth ───────────────────────────────────────────────────────

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(FITBIT_SCOPES),
            "state": state,
        }
        return f"{FITBIT_AUTH_URL}?{urllib.parse.urlencode(params)}"

    def exchange_code(self, code: str, redirect_uri: str) -> TokenInfo:
        if self._stub_mode:
            return TokenInfo(
                access_token=f"fitbit_stub_access_{code[:8]}",
                refresh_token=f"fitbit_stub_refresh_{code[:8]}",
                token_expires_at=datetime.now(tz=UTC) + timedelta(hours=8),
                scopes=FITBIT_SCOPES,
            )
        raise ProviderError("fitbit", "Real OAuth not implemented in MVP")

    def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        if self._stub_mode:
            return TokenInfo(
                access_token=f"fitbit_stub_refreshed_{refresh_token[:8]}",
                refresh_token=refresh_token,
                token_expires_at=datetime.now(tz=UTC) + timedelta(hours=8),
                scopes=FITBIT_SCOPES,
            )
        raise ProviderError("fitbit", "Real token refresh not implemented in MVP")

    def revoke_token(self, token: str) -> bool:
        if self._stub_mode:
            logger.info("Stub: revoking Fitbit token %s…", token[:8])
            return True
        raise ProviderError("fitbit", "Real token revocation not implemented in MVP")

    # ── Activity fetching ───────────────────────────────────────────

    def fetch_activities(
        self,
        access_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RawActivity]:
        if self._stub_mode:
            return self._generate_stub_activities(access_token, start_time, end_time)
        raise ProviderError("fitbit", "Real API fetch not implemented in MVP")

    # ── Stub helpers ────────────────────────────────────────────────

    def _generate_stub_activities(
        self,
        access_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RawActivity]:
        """Generate deterministic simulated Fitbit activities."""
        activities: list[RawActivity] = []
        seed = int(hashlib.md5(access_token.encode()).hexdigest()[:8], 16)  # noqa: S324

        current = start_time
        day_num = 0
        while current < end_time:
            day_seed = seed + day_num

            # Steps
            step_count = 4000 + (day_seed % 16000)
            activities.append(
                RawActivity(
                    external_id=f"fb_steps_{current.strftime('%Y%m%d')}_{day_seed:x}",
                    provider="fitbit",
                    activity_type="steps",
                    start_time=current.replace(hour=0, minute=0, second=0),
                    end_time=current.replace(hour=23, minute=59, second=59),
                    metrics={"step_count": step_count},
                    source_device="Fitbit Charge 6",
                )
            )

            # Workout (on odd day seeds)
            if day_seed % 2 == 1:
                duration = 25 + (day_seed % 35)
                intensities = ["light", "moderate", "vigorous"]
                intensity = intensities[day_seed % 3]
                activities.append(
                    RawActivity(
                        external_id=f"fb_workout_{current.strftime('%Y%m%d')}_{day_seed:x}",
                        provider="fitbit",
                        activity_type="workout",
                        start_time=current.replace(hour=18, minute=0),
                        end_time=current.replace(hour=18, minute=duration),
                        duration_minutes=duration,
                        intensity=intensity,
                        metrics={
                            "calories_burned": duration * 7,
                            "heart_rate_avg": 120 + (day_seed % 40),
                            "workout_type": "cycling",
                        },
                        source_device="Fitbit Charge 6",
                    )
                )

            # Active minutes
            active_mins = 10 + (day_seed % 50)
            activities.append(
                RawActivity(
                    external_id=f"fb_active_{current.strftime('%Y%m%d')}_{day_seed:x}",
                    provider="fitbit",
                    activity_type="active_minutes",
                    start_time=current.replace(hour=6, minute=0),
                    end_time=current.replace(hour=22, minute=0),
                    duration_minutes=active_mins,
                    intensity="moderate",
                    metrics={"active_minutes": active_mins},
                    source_device="Fitbit Charge 6",
                )
            )

            current += timedelta(days=1)
            day_num += 1

        return activities

    @staticmethod
    def _parse_real_activities(_data: dict[str, Any]) -> list[RawActivity]:
        """Parse real Fitbit API response into RawActivity list.

        Placeholder for production implementation.
        """
        return []  # pragma: no cover
