from typing import cast

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation, ensure_command_payload
from app.models.orders import (
    AllocateOrderRequest,
    AdjustAllocationRequest,
    AllocationMutationResponse,
    AllocationResponse,
    CancelOrderRequest,
    ConfirmOrderRequest,
    CreateOrderRequest,
    DeliverOrderRequest,
    FailDeliveryRequest,
    OrderDetail,
    OrderResponse,
    PackOrderRequest,
    ReleaseAllocationRequest,
    RequestCancelOrderRequest,
    ShipOrderRequest,
)
from app.services.orders import (
    adjust_allocation as adjust_allocation_service,
    allocate_order as allocate_order_service,
    cancel_order as cancel_order_service,
    confirm_order as confirm_order_service,
    create_order as create_order_service,
    deliver_order as deliver_order_service,
    fail_delivery as fail_delivery_service,
    get_order as get_order_service,
    pack_order as pack_order_service,
    release_allocation as release_allocation_service,
    request_cancel_order as request_cancel_order_service,
    ship_order as ship_order_service,
)

router = APIRouter()


@router.post("", response_model=OrderResponse, status_code=201)
def create_order(request: Request, payload: CreateOrderRequest) -> OrderResponse:
    return create_order_service(apply_request_correlation(request, payload))


@router.get("/{order_id}", response_model=OrderDetail)
def get_order(order_id: str) -> OrderDetail:
    return get_order_service(order_id)


@router.post("/{order_id}/confirm", response_model=OrderResponse)
def confirm_order(
    order_id: str,
    request: Request,
    payload: ConfirmOrderRequest | None = None,
) -> OrderResponse:
    return confirm_order_service(order_id, cast(ConfirmOrderRequest, ensure_command_payload(request, payload)))


@router.post("/{order_id}/allocate", response_model=AllocationResponse)
def allocate_order(order_id: str, request: Request, payload: AllocateOrderRequest) -> AllocationResponse:
    return allocate_order_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/allocations/{allocation_id}/adjust", response_model=AllocationMutationResponse)
def adjust_allocation(
    order_id: str,
    allocation_id: str,
    request: Request,
    payload: AdjustAllocationRequest,
) -> AllocationMutationResponse:
    return adjust_allocation_service(order_id, allocation_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/allocations/{allocation_id}/release", response_model=AllocationMutationResponse)
def release_allocation(
    order_id: str,
    allocation_id: str,
    request: Request,
    payload: ReleaseAllocationRequest,
) -> AllocationMutationResponse:
    return release_allocation_service(order_id, allocation_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/pack", response_model=OrderResponse)
def pack_order(order_id: str, request: Request, payload: PackOrderRequest) -> OrderResponse:
    return pack_order_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/ship", response_model=OrderResponse)
def ship_order(order_id: str, request: Request, payload: ShipOrderRequest) -> OrderResponse:
    return ship_order_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/deliver", response_model=OrderResponse)
def deliver_order(order_id: str, request: Request, payload: DeliverOrderRequest) -> OrderResponse:
    return deliver_order_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/fail-delivery", response_model=OrderResponse)
def fail_delivery(order_id: str, request: Request, payload: FailDeliveryRequest) -> OrderResponse:
    return fail_delivery_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/request-cancel", response_model=OrderResponse)
def request_cancel_order(
    order_id: str,
    request: Request,
    payload: RequestCancelOrderRequest,
) -> OrderResponse:
    return request_cancel_order_service(order_id, apply_request_correlation(request, payload))


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: str,
    request: Request,
    payload: CancelOrderRequest | None = None,
) -> OrderResponse:
    payload = apply_request_correlation(request, payload or CancelOrderRequest())
    return cancel_order_service(order_id, payload)
