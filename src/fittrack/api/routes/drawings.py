"""Drawing routes — /api/v1/drawings.

Public endpoints for viewing drawings and results.
Admin endpoints for managing drawing lifecycle and execution.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user_id, require_admin
from fittrack.api.schemas.drawings import DrawingCreate, DrawingUpdate

router = APIRouter(prefix="/api/v1/drawings", tags=["drawings"])


def _get_drawing_service():  # type: ignore[no-untyped-def]
    from fittrack.core.database import get_pool
    from fittrack.repositories.drawing_repository import DrawingRepository
    from fittrack.repositories.prize_repository import PrizeRepository
    from fittrack.repositories.ticket_repository import TicketRepository
    from fittrack.services.drawings import DrawingService

    pool = get_pool()
    return DrawingService(
        drawing_repo=DrawingRepository(pool),
        ticket_repo=TicketRepository(pool),
        prize_repo=PrizeRepository(pool),
    )


def _get_ticket_service():  # type: ignore[no-untyped-def]
    from fittrack.core.database import get_pool
    from fittrack.repositories.drawing_repository import DrawingRepository
    from fittrack.repositories.ticket_repository import TicketRepository
    from fittrack.repositories.transaction_repository import TransactionRepository
    from fittrack.repositories.user_repository import UserRepository
    from fittrack.services.tickets import TicketService

    pool = get_pool()
    return TicketService(
        ticket_repo=TicketRepository(pool),
        drawing_repo=DrawingRepository(pool),
        transaction_repo=TransactionRepository(pool),
        user_repo=UserRepository(pool),
    )


def _get_executor():  # type: ignore[no-untyped-def]
    from fittrack.core.database import get_pool
    from fittrack.repositories.drawing_repository import DrawingRepository
    from fittrack.repositories.fulfillment_repository import FulfillmentRepository
    from fittrack.repositories.prize_repository import PrizeRepository
    from fittrack.repositories.ticket_repository import TicketRepository
    from fittrack.services.drawing_executor import DrawingExecutor

    pool = get_pool()
    return DrawingExecutor(
        drawing_repo=DrawingRepository(pool),
        ticket_repo=TicketRepository(pool),
        prize_repo=PrizeRepository(pool),
        fulfillment_repo=FulfillmentRepository(pool),
    )


# ── Public endpoints ────────────────────────────────────────────────


@router.get("")
def list_drawings(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    drawing_type: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    """List drawings with pagination and optional filters."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.list_drawings(
            drawing_type=drawing_type, status=status, page=page, limit=limit
        )
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{drawing_id}")
def get_drawing(drawing_id: str) -> dict[str, Any]:
    """Get a drawing with prize details."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.get_drawing(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{drawing_id}/results")
def get_drawing_results(drawing_id: str) -> dict[str, Any]:
    """Get results for a completed drawing."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.get_results(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{drawing_id}/tickets", status_code=201)
def purchase_tickets(
    drawing_id: str,
    quantity: int = Query(default=1, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Purchase tickets for a drawing using points."""
    from fittrack.services.tickets import TicketError

    service = _get_ticket_service()
    try:
        return service.purchase_tickets(
            user_id=user_id, drawing_id=drawing_id, quantity=quantity
        )
    except TicketError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.get("/{drawing_id}/my-tickets")
def get_my_tickets(
    drawing_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get current user's tickets for a drawing."""
    service = _get_ticket_service()
    return service.get_user_tickets(user_id, drawing_id)


# ── Admin endpoints ─────────────────────────────────────────────────


@router.post("", status_code=201)
def create_drawing(
    body: DrawingCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new drawing (admin only)."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.create_drawing(
            drawing_type=body.drawing_type,
            name=body.name,
            description=body.description,
            ticket_cost_points=body.ticket_cost_points,
            drawing_time=body.drawing_time,
            eligibility=body.eligibility,
            created_by=body.created_by,
        )
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.patch("/{drawing_id}")
def update_drawing(
    drawing_id: str,
    body: DrawingUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Update a drawing (admin only)."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.drawing_repository import DrawingRepository

    repo = DrawingRepository(pool=get_pool())
    data = body.model_dump(exclude_none=True, mode="json")
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    affected = repo.update(drawing_id, data=data)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Drawing not found")
    return {"drawing_id": drawing_id, "updated": True}


@router.post("/{drawing_id}/execute")
def execute_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Execute a drawing — select winners (admin only)."""
    from fittrack.services.drawing_executor import ExecutionError

    executor = _get_executor()
    try:
        return executor.execute(drawing_id)
    except ExecutionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{drawing_id}/schedule")
def schedule_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Schedule a draft drawing (admin only)."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.schedule_drawing(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{drawing_id}/open")
def open_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Open ticket sales for a drawing (admin only)."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.open_drawing(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{drawing_id}/close")
def close_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Close ticket sales for a drawing (admin only)."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.close_drawing(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{drawing_id}/cancel")
def cancel_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Cancel a drawing (admin only)."""
    from fittrack.services.drawings import DrawingError

    service = _get_drawing_service()
    try:
        return service.cancel_drawing(drawing_id)
    except DrawingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.delete("/{drawing_id}", status_code=204)
def delete_drawing(
    drawing_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> None:
    """Delete a drawing (admin only)."""
    from fittrack.core.database import get_pool
    from fittrack.repositories.drawing_repository import DrawingRepository

    repo = DrawingRepository(pool=get_pool())
    affected = repo.delete(drawing_id)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Drawing not found")
