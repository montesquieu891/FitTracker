"""Point transaction CRUD routes — /api/v1/transactions."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query

from fittrack.api.deps import get_current_user
from fittrack.api.schemas.transactions import TransactionCreate
from fittrack.repositories.transaction_repository import TransactionRepository

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


def _get_repo() -> TransactionRepository:
    from fittrack.core.database import get_pool

    return TransactionRepository(pool=get_pool())


@router.get("")
def list_transactions(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str | None = None,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    """List point transactions with pagination."""
    repo = _get_repo()
    filters: dict[str, Any] = {}
    if user_id:
        filters["user_id"] = user_id
    if transaction_type:
        filters["transaction_type"] = transaction_type

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
def create_transaction(
    body: TransactionCreate,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new point transaction."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"transaction_id": new_id, **data}
