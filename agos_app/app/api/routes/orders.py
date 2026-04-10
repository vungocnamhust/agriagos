from fastapi import APIRouter

from app.models.orders import (
    AllocateOrderRequest,
    AllocationResponse,
    CancelOrderRequest,
    CreateOrderRequest,
    DeliverOrderRequest,
    OrderDetail,
    OrderResponse,
    PackOrderRequest,
    RequestCancelOrderRequest,
    ShipOrderRequest,
)
from app.services import orders as svc

router = APIRouter()


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(payload: CreateOrderRequest) -> OrderResponse:
    return svc.create_order(payload)


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: str) -> OrderDetail:
    return svc.get_order(order_id)


@router.post("/{order_id}/confirm", response_model=OrderResponse)
def confirm_order(order_id: str) -> OrderResponse:
    return svc.confirm_order(order_id)


@router.post("/{order_id}/allocate", response_model=AllocationResponse)
def allocate_order(order_id: str, payload: AllocateOrderRequest) -> AllocationResponse:
    return svc.allocate_order(order_id, payload)


@router.post("/{order_id}/pack", response_model=OrderResponse)
def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    return svc.pack_order(order_id, payload)


@router.post("/{order_id}/ship", response_model=OrderResponse)
def ship_order(order_id: str, payload: ShipOrderRequest) -> OrderResponse:
    return svc.ship_order(order_id, payload)


@router.post("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order(order_id: str, payload: DeliverOrderRequest) -> OrderResponse:
    return svc.deliver_order(order_id, payload)


@router.post("/{order_id}/request-cancel", response_model=OrderResponse)
def request_cancel_order(
    order_id: str,
    payload: RequestCancelOrderRequest,
) -> OrderResponse:
    return svc.request_cancel_order(order_id, payload)


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: str,
    payload: CancelOrderRequest | None = None,
) -> OrderResponse:
    return svc.cancel_order(order_id, payload)
