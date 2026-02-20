"""Sponsor CRUD routes — /api/v1/sponsors."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import require_admin
from fittrack.api.schemas.sponsors import SponsorCreate, SponsorUpdate
from fittrack.repositories.sponsor_repository import SponsorRepository

router = APIRouter(prefix="/api/v1/sponsors", tags=["sponsors"])


def _get_repo() -> SponsorRepository:
    from fittrack.core.database import get_pool
    return SponsorRepository(pool=get_pool())


@router.get("")
def list_sponsors(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """List sponsors with pagination."""
    repo = _get_repo()
    total = repo.count()
    offset = (page - 1) * limit
    items = repo.find_all(limit=limit, offset=offset)
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


@router.post("", status_code=201)
def create_sponsor(
    body: SponsorCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new sponsor."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"sponsor_id": new_id, **data}


@router.get("/{sponsor_id}")
def get_sponsor(sponsor_id: str) -> dict[str, Any]:
    """Get a sponsor by ID."""
    repo = _get_repo()
    sponsor = repo.find_by_id(sponsor_id)
    if sponsor is None:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    return sponsor


@router.patch("/{sponsor_id}")
def update_sponsor(
    sponsor_id: str,
    body: SponsorUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Update a sponsor."""
    repo = _get_repo()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    affected = repo.update(sponsor_id, data=data)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Sponsor not found")
    return {"sponsor_id": sponsor_id, "updated": True}


@router.delete("/{sponsor_id}", status_code=204)
def delete_sponsor(
    sponsor_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> None:
    """Delete a sponsor."""
    repo = _get_repo()
    affected = repo.delete(sponsor_id)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Sponsor not found")
