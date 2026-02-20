"""Prize CRUD routes — /api/v1/prizes."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from fittrack.api.deps import require_admin
from fittrack.api.schemas.prizes import PrizeCreate
from fittrack.repositories.prize_repository import PrizeRepository

router = APIRouter(prefix="/api/v1/prizes", tags=["prizes"])


def _get_repo() -> PrizeRepository:
    from fittrack.core.database import get_pool
    return PrizeRepository(pool=get_pool())


@router.get("")
def list_prizes(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    drawing_id: str | None = None,
) -> dict[str, Any]:
    """List prizes with pagination."""
    repo = _get_repo()
    filters: dict[str, Any] = {}
    if drawing_id:
        filters["drawing_id"] = drawing_id

    total = repo.count(filters=filters)
    offset = (page - 1) * limit
    items = repo.find_all(limit=limit, offset=offset, filters=filters)
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
def create_prize(
    body: PrizeCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new prize."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"prize_id": new_id, **data}
