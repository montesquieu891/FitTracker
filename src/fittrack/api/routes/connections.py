"""Tracker connection routes — /api/v1/connections.

CP4: Fully service-backed with OAuth flow endpoints.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user, get_current_user_id

router = APIRouter(prefix="/api/v1/connections", tags=["connections"])


def _get_tracker_service():  # type: ignore[no-untyped-def]
    from fittrack.core.database import get_pool
    from fittrack.repositories.connection_repository import ConnectionRepository
    from fittrack.services.providers.fitbit import FitbitProvider
    from fittrack.services.providers.google_fit import GoogleFitProvider
    from fittrack.services.trackers import TrackerService

    pool = get_pool()
    connection_repo = ConnectionRepository(pool)
    providers = {
        "google_fit": GoogleFitProvider(),
        "fitbit": FitbitProvider(),
    }
    return TrackerService(connection_repo=connection_repo, providers=providers)


@router.get("")
def list_connections(
    user_id: str = Depends(get_current_user_id),
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """List current user's tracker connections (tokens stripped)."""
    service = _get_tracker_service()
    connections = service.get_user_connections(user_id)
    return {"items": connections, "count": len(connections)}


@router.post("/{provider}/initiate", status_code=200)
def initiate_oauth(
    provider: str,
    redirect_uri: str = Query(description="OAuth callback URL"),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Start OAuth flow for a tracker provider."""
    from fittrack.services.trackers import TrackerError

    if provider not in ("google_fit", "fitbit"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    service = _get_tracker_service()
    try:
        return service.initiate_oauth(user_id, provider, redirect_uri)
    except TrackerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{provider}/callback", status_code=201)
def complete_oauth(
    provider: str,
    code: str = Query(description="Authorization code from provider"),
    redirect_uri: str = Query(description="Same redirect_uri used in initiate"),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Complete OAuth flow — exchange code for tokens and create connection."""
    from fittrack.services.trackers import TrackerError

    if provider not in ("google_fit", "fitbit"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    service = _get_tracker_service()
    try:
        return service.complete_oauth(user_id, provider, code, redirect_uri)
    except TrackerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.delete("/{provider}", status_code=200)
def disconnect_provider(
    provider: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Disconnect a tracker provider — revokes token and deletes connection."""
    from fittrack.services.trackers import TrackerError

    if provider not in ("google_fit", "fitbit"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    service = _get_tracker_service()
    try:
        service.disconnect(user_id, provider)
        return {"message": f"Disconnected from {provider}"}
    except TrackerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{provider}/sync", status_code=200)
def force_sync(
    provider: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Force an immediate sync for a provider (rate limited)."""
    from fittrack.services.trackers import TrackerError

    if provider not in ("google_fit", "fitbit"):
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    service = _get_tracker_service()
    try:
        return service.force_sync(user_id, provider)
    except TrackerError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
