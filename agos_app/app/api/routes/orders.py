from fastapi import APIRouter, HTTPException
from app.models.orders import (
    CreateOrderRequest,
    OrderResponse,
    OrderDetail,
    AllocateOrderRequest,
    AllocationResponse,
    PackOrderRequest,
    ShipOrderRequest,
    DeliverOrderRequest,
    RequestCancelOrderRequest,
    CancelOrderRequest,
)

router = APIRouter()

@router.post("", response_model=OrderResponse, status_code=201)
def create_order(payload: CreateOrderRequest) -> OrderResponse:
    # TODO: create order + order lines, append OrderCreated event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: str) -> OrderDetail:
    # TODO: load order detail
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/confirm", response_model=OrderResponse)
def confirm_order(order_id: str) -> OrderResponse:
    # TODO: enforce state transition, append OrderConfirmed event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/allocate", response_model=AllocationResponse)
def allocate_order(order_id: str, payload: AllocateOrderRequest) -> AllocationResponse:
    # TODO: validate released lots, quota, inventory movement, append OrderAllocated event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/pack", response_model=OrderResponse)
def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    # TODO: validate allocations, write packing state, append OrderPacked event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/ship", response_model=OrderResponse)
def ship_order(order_id: str, payload: ShipOrderRequest) -> OrderResponse:
    # TODO: append OrderShipped event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order(order_id: str, payload: DeliverOrderRequest) -> OrderResponse:
    # TODO: append OrderDelivered event and consume preorder delivered qty
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/request-cancel", response_model=OrderResponse)
def request_cancel_order(order_id: str, payload: RequestCancelOrderRequest) -> OrderResponse:
    # TODO: record cancel request, maybe require approval depending on current state
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(order_id: str, payload: CancelOrderRequest | None = None) -> OrderResponse:
    # TODO: execute cancellation after policy/approval
    raise HTTPException(status_code=501, detail="Not implemented")
