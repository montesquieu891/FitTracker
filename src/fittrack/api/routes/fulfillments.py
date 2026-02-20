"""Fulfillment routes — /api/v1/fulfillments.

Admin endpoints for managing prize fulfillment lifecycle.
Winner endpoint for confirming shipping address.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from fittrack.api.deps import get_current_user_id, require_admin
from fittrack.api.schemas.fulfillments import FulfillmentCreate, FulfillmentUpdate

if TYPE_CHECKING:
    from fittrack.services.fulfillments import FulfillmentService

router = APIRouter(prefix="/api/v1/fulfillments", tags=["fulfillments"])


def _get_service() -> FulfillmentService:
    from fittrack.core.database import get_pool
    from fittrack.repositories.fulfillment_repository import FulfillmentRepository
    from fittrack.services.fulfillments import FulfillmentService

    return FulfillmentService(fulfillment_repo=FulfillmentRepository(pool=get_pool()))


@router.get("")
def list_fulfillments(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user_id: str | None = None,
    status: str | None = None,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """List fulfillments with pagination (admin only)."""
    service = _get_service()
    return service.list_fulfillments(user_id=user_id, status=status, page=page, limit=limit)


@router.get("/{fulfillment_id}")
def get_fulfillment(
    fulfillment_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Get a fulfillment by ID (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    try:
        return service.get_fulfillment(fulfillment_id)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("", status_code=201)
def create_fulfillment(
    body: FulfillmentCreate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Create a new fulfillment record (admin only)."""
    import uuid

    from fittrack.core.database import get_pool
    from fittrack.repositories.fulfillment_repository import FulfillmentRepository

    repo = FulfillmentRepository(pool=get_pool())
    new_id = uuid.uuid4().hex
    data = body.model_dump(exclude_none=True)
    repo.create(data=data, new_id=new_id)
    return {"fulfillment_id": new_id, **data}


@router.put("/{fulfillment_id}")
def update_fulfillment(
    fulfillment_id: str,
    body: FulfillmentUpdate,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Update a fulfillment status (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    new_status = data.get("status")
    if new_status:
        try:
            return service.transition_status(
                fulfillment_id,
                new_status,
                **{k: v for k, v in data.items() if k != "status"},
            )
        except FulfillmentError as e:
            raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    # Non-status updates (notes, etc.)
    from fittrack.core.database import get_pool
    from fittrack.repositories.fulfillment_repository import FulfillmentRepository

    repo = FulfillmentRepository(pool=get_pool())
    affected = repo.update(fulfillment_id, data=data)
    if affected == 0:
        raise HTTPException(status_code=404, detail="Fulfillment not found")
    return {"fulfillment_id": fulfillment_id, "updated": True}


@router.post("/{fulfillment_id}/notify")
def notify_winner(
    fulfillment_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Mark winner as notified (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    try:
        return service.notify_winner(fulfillment_id)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{fulfillment_id}/ship")
def ship_prize(
    fulfillment_id: str,
    carrier: str = Query(...),
    tracking_number: str = Query(...),
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Mark prize as shipped with tracking info (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    try:
        return service.ship_prize(fulfillment_id, carrier=carrier, tracking_number=tracking_number)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{fulfillment_id}/deliver")
def mark_delivered(
    fulfillment_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Mark prize as delivered (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    try:
        return service.mark_delivered(fulfillment_id)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{fulfillment_id}/confirm-address")
def confirm_address(
    fulfillment_id: str,
    address: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Winner confirms their shipping address."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()

    # Verify this fulfillment belongs to the requesting user
    try:
        f = service.get_fulfillment(fulfillment_id)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e

    if f.get("user_id") != user_id:
        raise HTTPException(status_code=403, detail="Not your fulfillment")

    try:
        return service.confirm_address(fulfillment_id, address)
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post("/{fulfillment_id}/forfeit")
def forfeit_prize(
    fulfillment_id: str,
    _admin: dict[str, Any] = Depends(require_admin),
) -> dict[str, Any]:
    """Forfeit a prize (admin only)."""
    from fittrack.services.fulfillments import FulfillmentError

    service = _get_service()
    try:
        return service.forfeit(fulfillment_id, reason="Admin forfeiture")
    except FulfillmentError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
