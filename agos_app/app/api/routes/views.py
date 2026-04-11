from fastapi import APIRouter

from app.models.views import Customer360View
from app.services import views as svc

router = APIRouter()


@router.get("/customer-360/{customer_id}", response_model=Customer360View)
def get_customer_360(customer_id: str) -> Customer360View:
    return svc.get_customer_360(customer_id)


@router.get("/available-lots")
def get_available_lots_board(skuId: str | None = None) -> dict:
    return svc.get_available_lots_board(skuId)


@router.get("/pending-fulfillment")
def get_pending_fulfillment() -> dict:
    return svc.get_pending_fulfillment()


@router.get("/farm")
def get_farm_view() -> dict:
    return svc.get_farm_view()
