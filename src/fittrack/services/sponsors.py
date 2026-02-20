"""Sponsor service — CRUD with status management for prize sponsors."""

from __future__ import annotations

import logging
from typing import Any

from fittrack.core.constants import SPONSOR_STATUSES

logger = logging.getLogger(__name__)


class SponsorError(Exception):
    """Sponsor service error with HTTP status hint."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class SponsorService:
    """Manages sponsor CRUD and status transitions."""

    def __init__(self, sponsor_repo: Any) -> None:
        self.sponsor_repo = sponsor_repo

    def create_sponsor(self, **data: Any) -> dict[str, Any]:
        """Create a new sponsor."""
        from fittrack.repositories.base import BaseRepository

        name = data.get("name")
        if not name:
            raise SponsorError("Sponsor name is required")

        status = data.get("status", "active")
        if status not in SPONSOR_STATUSES:
            raise SponsorError(f"Invalid status: {status}")

        sponsor_id = BaseRepository._generate_id()
        self.sponsor_repo.create(data=data, new_id=sponsor_id)
        return {"sponsor_id": sponsor_id, **data}

    def get_sponsor(self, sponsor_id: str) -> dict[str, Any]:
        """Get a sponsor by ID."""
        sponsor = self.sponsor_repo.find_by_id(sponsor_id)
        if sponsor is None:
            raise SponsorError("Sponsor not found", status_code=404)
        return sponsor

    def update_sponsor(
        self, sponsor_id: str, **data: Any
    ) -> dict[str, Any]:
        """Update a sponsor."""
        sponsor = self.sponsor_repo.find_by_id(sponsor_id)
        if sponsor is None:
            raise SponsorError("Sponsor not found", status_code=404)

        if "status" in data and data["status"] not in SPONSOR_STATUSES:
            raise SponsorError(f"Invalid status: {data['status']}")

        filtered = {k: v for k, v in data.items() if v is not None}
        if not filtered:
            raise SponsorError("No fields to update")

        self.sponsor_repo.update(sponsor_id, data=filtered)
        sponsor.update(filtered)
        return sponsor

    def deactivate_sponsor(self, sponsor_id: str) -> dict[str, Any]:
        """Set sponsor status to inactive."""
        return self.update_sponsor(sponsor_id, status="inactive")

    def activate_sponsor(self, sponsor_id: str) -> dict[str, Any]:
        """Set sponsor status to active."""
        return self.update_sponsor(sponsor_id, status="active")

    def list_sponsors(
        self,
        *,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List sponsors with optional status filter."""
        filters: dict[str, Any] = {}
        if status:
            if status not in SPONSOR_STATUSES:
                raise SponsorError(f"Invalid status filter: {status}")
            filters["status"] = status

        total = self.sponsor_repo.count(filters=filters)
        offset = (page - 1) * limit
        items = self.sponsor_repo.find_all(
            limit=limit, offset=offset, filters=filters
        )
        total_pages = max(1, (total + limit - 1) // limit)

        return {
            "items": items,
            "pagination": {
                "page": page,
                "limit": limit,
                "total_items": total,
                "total_pages": total_pages,
            },
        }

    def delete_sponsor(self, sponsor_id: str) -> bool:
        """Delete a sponsor. Returns True if deleted."""
        sponsor = self.sponsor_repo.find_by_id(sponsor_id)
        if sponsor is None:
            raise SponsorError("Sponsor not found", status_code=404)
        affected = self.sponsor_repo.delete(sponsor_id)
        return affected > 0
