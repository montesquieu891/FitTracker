"""Abstract base class for fitness tracker providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RawActivity:
    """Unified raw activity from any provider before normalization.

    Every provider returns activities in this format so the normalizer
    can process them uniformly.
    """

    external_id: str
    provider: str  # "google_fit" | "fitbit"
    activity_type: str  # "steps" | "workout" | "active_minutes"
    start_time: datetime
    end_time: datetime | None = None
    duration_minutes: int | None = None
    intensity: str | None = None  # "light" | "moderate" | "vigorous"
    metrics: dict[str, Any] = field(default_factory=dict)
    source_device: str | None = None


@dataclass
class TokenInfo:
    """OAuth token information for a provider connection."""

    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None
    scopes: list[str] = field(default_factory=list)


class ProviderError(Exception):
    """Error communicating with or processing data from a provider."""

    def __init__(self, provider: str, detail: str, retriable: bool = False) -> None:
        self.provider = provider
        self.detail = detail
        self.retriable = retriable
        super().__init__(f"[{provider}] {detail}")


class BaseProvider(ABC):
    """Abstract base for fitness tracker providers (Google Fit, Fitbit).

    Subclasses implement the actual API calls; the sync worker calls
    them through this interface.
    """

    provider_name: str = ""

    @abstractmethod
    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Return the OAuth authorization URL for this provider."""

    @abstractmethod
    def exchange_code(self, code: str, redirect_uri: str) -> TokenInfo:
        """Exchange an authorization code for tokens."""

    @abstractmethod
    def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        """Use a refresh token to get a new access token."""

    @abstractmethod
    def revoke_token(self, token: str) -> bool:
        """Revoke a token (disconnect). Returns True on success."""

    @abstractmethod
    def fetch_activities(
        self,
        access_token: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[RawActivity]:
        """Fetch activities from the provider API for the given time range.

        Returns a list of RawActivity objects ready for normalization.
        """

    def validate_token(self, access_token: str) -> bool:
        """Check if an access token is still valid.

        Default implementation always returns True.
        Providers can override for explicit validation.
        """
        return True
