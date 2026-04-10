from fastapi import APIRouter, HTTPException
from app.models.views import Customer360View

router = APIRouter()

@router.get("/customer-360/{customer_id}", response_model=Customer360View)
def get_customer_360(customer_id: str) -> Customer360View:
    # TODO: return customer 360 read model
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/available-lots")
def get_available_lots_board(skuId: str | None = None) -> dict:
    # TODO: return released/available lots board
    return {"items": []}

@router.get("/pending-fulfillment")
def get_pending_fulfillment() -> dict:
    # TODO: return pending fulfillment board
    return {"items": []}

@router.get("/farm")
def get_farm_view() -> dict:
    # TODO: return farm summary read model
    return {"plots": [], "cropCycles": []}
