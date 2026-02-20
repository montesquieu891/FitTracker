"""User CRUD routes — /api/v1/users."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import require_admin
from fittrack.api.schemas.users import UserCreate, UserUpdate
from fittrack.repositories.user_repository import UserRepository

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _get_repo() -> UserRepository:
    from fittrack.core.database import get_pool

    return UserRepository(pool=get_pool())


@router.get("")
def list_users(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    status: str | None = None,
) -> dict[str, Any]:
    """List users with pagination."""
    repo = _get_repo()
    filters: dict[str, Any] = {}
    if status:
        filters["status"] = status

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
def create_user(
    body: UserCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new user."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"user_id": new_id, **data}


@router.get("/{user_id}")
def get_user(user_id: str) -> dict[str, Any]:
    """Get a user by ID."""
    repo = _get_repo()
    user = repo.find_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Update a user."""
    repo = _get_repo()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    affected = repo.update(user_id, data=data)
    if affected == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "updated": True}


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> None:
    """Delete a user."""
    repo = _get_repo()
    affected = repo.delete(user_id)
    if affected == 0:
        raise HTTPException(status_code=404, detail="User not found")
