"""Activity routes — /api/v1/activities.

CP4: Activity listing with filters, activity summary, and point-aware creation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query

from fittrack.api.deps import get_current_user, get_current_user_id
from fittrack.api.schemas.activities import ActivityCreate
from fittrack.repositories.activity_repository import ActivityRepository

router = APIRouter(prefix="/api/v1/activities", tags=["activities"])


def _get_repo() -> ActivityRepository:
    from fittrack.core.database import get_pool
    return ActivityRepository(pool=get_pool())


@router.get("")
def list_activities(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    activity_type: str | None = None,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """List the current user's activities with pagination and optional filters."""
    repo = _get_repo()
    filters: dict[str, Any] = {"user_id": user_id}
    if activity_type:
        filters["activity_type"] = activity_type

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


@router.get("/summary")
def activity_summary(
    period: str = Query(default="today", pattern=r"^(today|week|month)$"),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get activity summary for today, this week, or this month."""
    repo = _get_repo()
    now = datetime.now(tz=UTC)

    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    else:  # month
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    end = now

    try:
        activities = repo.find_by_user_and_date_range(user_id, start, end)
    except Exception:
        activities = []

    total_steps = 0
    total_active_minutes = 0
    workout_count = 0
    total_points = 0
    total_calories = 0

    for a in activities:
        metrics = a.get("metrics", {})
        if isinstance(metrics, str):
            import json
            try:
                metrics = json.loads(metrics)
            except (json.JSONDecodeError, TypeError):
                metrics = {}

        atype = a.get("activity_type", "")
        if atype == "steps":
            total_steps += metrics.get("step_count", 0)
        elif atype == "workout":
            workout_count += 1
            total_calories += metrics.get("calories_burned", 0)
        elif atype == "active_minutes":
            total_active_minutes += a.get("duration_minutes", 0) or metrics.get(
                "active_minutes", 0
            )

        total_points += a.get("points_earned", 0)

    return {
        "period": period,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total_steps": total_steps,
        "total_active_minutes": total_active_minutes,
        "workout_count": workout_count,
        "total_points": total_points,
        "total_calories": total_calories,
        "activity_count": len(activities),
    }


@router.post("", status_code=201)
def create_activity(
    body: ActivityCreate,
    _user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a new activity."""
    repo = _get_repo()
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True, mode="json")
    repo.create(data=data, new_id=new_id)
    return {"activity_id": new_id, **data}
