from fastapi import APIRouter

from app.models.farm import FarmView
from app.models.views import AvailableLotListResponse, Customer360View, PendingFulfillmentListResponse
from app.services import views as svc

router = APIRouter()


@router.get("/customer-360/{customer_id}", response_model=Customer360View)
def get_customer_360(customer_id: str) -> Customer360View:
    return svc.get_customer_360(customer_id)


@router.get("/available-lots", response_model=AvailableLotListResponse)
def get_available_lots_board(skuId: str | None = None) -> AvailableLotListResponse:
    return svc.get_available_lots_board(skuId)


@router.get("/pending-fulfillment", response_model=PendingFulfillmentListResponse)
def get_pending_fulfillment() -> PendingFulfillmentListResponse:
    return svc.get_pending_fulfillment()


@router.get("/farm", response_model=FarmView)
def get_farm_view() -> FarmView:
    return svc.get_farm_view()
