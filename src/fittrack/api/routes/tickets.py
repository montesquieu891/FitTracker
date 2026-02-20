"""Ticket CRUD routes — /api/v1/tickets."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from fittrack.api.deps import get_current_user
from fittrack.api.schemas.tickets import TicketCreate
from fittrack.repositories.ticket_repository import TicketRepository

router = APIRouter(prefix="/api/v1/tickets", tags=["tickets"])


def _get_repo() -> TicketRepository:
    from fittrack.core.database import get_pool
    return TicketRepository(pool=get_pool())


@router.get("")
def list_tickets(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    drawing_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """List tickets with pagination."""
    repo = _get_repo()
    filters: dict[str, Any] = {}
    if drawing_id:
        filters["drawing_id"] = drawing_id
    if user_id:
        filters["user_id"] = user_id

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
def create_ticket(
    body: TicketCreate,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new ticket."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"ticket_id": new_id, **data}
