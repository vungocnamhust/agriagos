import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.gateway import (
    assert_order_transition,
    check_idempotency,
    record_idempotency,
)
from app.models.enums import AllocationStatus, LotStatus, OrderStatus, PaymentStatus, PreorderStatus
from app.models.orders import (
    AllocateOrderRequest,
    AllocationItemResponse,
    AllocationResponse,
    CancelOrderRequest,
    CreateOrderRequest,
    DeliverOrderRequest,
    OrderDetail,
    OrderLine,
    OrderResponse,
    PackOrderRequest,
    RequestCancelOrderRequest,
    ShipOrderRequest,
)
from app.store import postgres_sync
from app.store import memory as store


def _new_order_code() -> str:
    return f"ORD-{str(uuid.uuid4())[:8].upper()}"


def _build_order_detail(record: dict[str, Any]) -> OrderDetail:
    lines = [OrderLine(**ln) for ln in record.get("lines", [])]
    return OrderDetail(
        orderId=record["orderId"],
        orderCode=record["orderCode"],
        customerId=record["customerId"],
        channel=record["channel"],
        status=record["status"],
        paymentStatus=record["paymentStatus"],
        deliveryDateExpected=record.get("deliveryDateExpected"),
        lines=lines,
    )


def _get_order_record_or_404(order_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_order(order_id)
    else:
        record = store._orders.get(order_id)

    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")
    return record


def _get_lot_record_or_404(lot_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        lot = postgres_sync.fetch_lot(lot_id)
    else:
        lot = store._lots.get(lot_id)

    if not lot:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found.")
    return lot


def _get_allocations_for_order(order_id: str) -> list[dict[str, Any]]:
    if postgres_sync.is_enabled():
        return postgres_sync.fetch_allocations_for_order(order_id)
    return list(store._allocations.get(order_id, []))


def create_order(payload: CreateOrderRequest) -> OrderResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    customer_exists = payload.customerId in store._customers
    if postgres_sync.is_enabled():
        customer_exists = postgres_sync.customer_exists(payload.customerId)

    if not customer_exists:
        raise HTTPException(status_code=404, detail="Customer not found.")

    order_id = str(uuid.uuid4())
    order_code = _new_order_code()
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

    lines = [
        {
            "orderLineId": str(uuid.uuid4()),
            "productSkuId": ln.productSkuId,
            "orderedQty": ln.orderedQty,
            "allocatedQty": 0.0,
            "packedQty": 0.0,
            "deliveredQty": 0.0,
            "unit": ln.unit,
            "sourcePreorderId": ln.sourcePreorderId,
        }
        for ln in payload.lines
    ]

    record: dict[str, Any] = {
        "orderId": order_id,
        "orderCode": order_code,
        "customerId": payload.customerId,
        "channel": payload.channel,
        "status": OrderStatus.draft.value,
        "paymentStatus": PaymentStatus.unpaid.value,
        "deliveryDateExpected": payload.deliveryDateExpected,
        "shippingAddress": payload.shippingAddress,
        "paymentIntent": payload.paymentIntent,
        "note": payload.note,
        "lines": lines,
    }
    postgres_sync.upsert_order(record)
    if not postgres_sync.is_enabled():
        store._orders[order_id] = record

    events.emit(
        event_name="order.created",
        aggregate_type="Order",
        aggregate_id=order_id,
        payload=record,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def get_order(order_id: str) -> OrderDetail:
    record = _get_order_record_or_404(order_id)
    return _build_order_detail(record)


def confirm_order(order_id: str) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    next_status = assert_order_transition(record, "confirm")
    record["status"] = next_status
    postgres_sync.upsert_order(record)
    events.emit("order.confirmed", "Order", order_id, {"orderId": order_id, "status": next_status})
    return OrderResponse(data=_build_order_detail(record))


def allocate_order(order_id: str, payload: AllocateOrderRequest) -> AllocationResponse:
    record = _get_order_record_or_404(order_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return AllocationResponse(**cached)

    next_status = assert_order_transition(record, "allocate")

    existing_allocations = _get_allocations_for_order(order_id)
    all_allocations = list(existing_allocations)
    new_allocations: list[dict[str, Any]] = []
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}

    for item in payload.allocations:
        lot = _get_lot_record_or_404(item.lotId)
        if lot["status"] != LotStatus.released.value:
            raise HTTPException(
                status_code=422,
                detail=f"Lot {item.lotId} is not in released state (current: {lot['status']}).",
            )
        if lot["availableQty"] < item.allocatedQty:
            raise HTTPException(
                status_code=422,
                detail=f"Lot {item.lotId} has insufficient available qty ({lot['availableQty']}).",
            )
        if item.orderLineId not in line_map:
            raise HTTPException(status_code=422, detail=f"OrderLine {item.orderLineId} not found.")

        # Reserve inventory
        line_map[item.orderLineId]["allocatedQty"] += item.allocatedQty

        allocation_id = str(uuid.uuid4())
        alloc_record = {
            "allocationId": allocation_id,
            "orderLineId": item.orderLineId,
            "lotId": item.lotId,
            "allocatedQty": item.allocatedQty,
            "status": AllocationStatus.active.value,
        }
        all_allocations.append(alloc_record)
        new_allocations.append(alloc_record)

        if not postgres_sync.is_enabled():
            lot["availableQty"] -= item.allocatedQty
            lot["reservedQty"] = lot.get("reservedQty", 0.0) + item.allocatedQty

    if postgres_sync.is_enabled():
        try:
            postgres_sync.allocate_order_atomic(order_id, next_status, new_allocations)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        record = _get_order_record_or_404(order_id)
    else:
        record["status"] = next_status
        postgres_sync.upsert_order(record)
        store._allocations[order_id] = all_allocations

    events.emit(
        "order.allocated",
        "Order",
        order_id,
        {"orderId": order_id, "allocations": new_allocations},
    )

    result = AllocationResponse(
        orderId=order_id,
        allocations=[AllocationItemResponse(**a) for a in new_allocations],
    )
    record_idempotency(key, result.model_dump())
    return result


def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "pack")
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}

    for item in payload.packedQtySummary:
        if item.orderLineId not in line_map:
            raise HTTPException(status_code=422, detail=f"OrderLine {item.orderLineId} not found.")
        line_map[item.orderLineId]["packedQty"] = item.packedQty

    record["status"] = next_status
    postgres_sync.upsert_order(record)
    events.emit("order.packed", "Order", order_id, {"orderId": order_id, "status": next_status})

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def ship_order(order_id: str, payload: ShipOrderRequest) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "ship")
    record["status"] = next_status
    record["carrier"] = payload.carrier
    record["trackingRef"] = payload.trackingRef
    record["shippedAt"] = payload.shippedAt
    postgres_sync.upsert_order(record)

    events.emit(
        "order.shipped",
        "Order",
        order_id,
        {"orderId": order_id, "carrier": payload.carrier, "trackingRef": payload.trackingRef},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def deliver_order(order_id: str, payload: DeliverOrderRequest) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "deliver")
    record["status"] = next_status
    record["deliveredAt"] = payload.deliveredAt
    record["proofRef"] = payload.proofRef
    postgres_sync.upsert_order(record)

    # Consume preorder delivered qty for any lines linked to a preorder
    for line in record["lines"]:
        if line.get("sourcePreorderId"):
            if postgres_sync.is_enabled():
                preorder = None
            else:
                preorder = store._preorders.get(line["sourcePreorderId"])

            qty = line.get("deliveredQty", 0.0) or line.get("allocatedQty", 0.0)
            if postgres_sync.is_enabled():
                postgres_sync.increment_preorder_delivered_qty_atomic(line["sourcePreorderId"], qty)
            elif preorder:
                preorder["deliveredQty"] = preorder.get("deliveredQty", 0.0) + qty
                preorder["remainingQty"] = max(
                    0.0,
                    preorder["committedQty"] - preorder["deliveredQty"],
                )
                if preorder["remainingQty"] == 0:
                    preorder["status"] = PreorderStatus.completed.value
                postgres_sync.upsert_preorder(preorder)

    events.emit(
        "order.delivered",
        "Order",
        order_id,
        {"orderId": order_id, "deliveredAt": payload.deliveredAt},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def request_cancel_order(order_id: str, payload: RequestCancelOrderRequest) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "request_cancel")
    record["status"] = next_status
    record["cancelReason"] = payload.reason
    postgres_sync.upsert_order(record)

    events.emit(
        "order.cancel_requested",
        "Order",
        order_id,
        {"orderId": order_id, "reason": payload.reason},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def cancel_order(order_id: str, payload: CancelOrderRequest | None) -> OrderResponse:
    record = _get_order_record_or_404(order_id)

    meta = payload.meta if payload else None
    key = meta.idempotencyKey if meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "cancel")
    allocations = _get_allocations_for_order(order_id)

    # Release reserved inventory back to lots
    if postgres_sync.is_enabled():
        postgres_sync.cancel_order_atomic(order_id, next_status)
        record = _get_order_record_or_404(order_id)
        allocations = _get_allocations_for_order(order_id)
    else:
        for alloc in allocations:
            lot = _get_lot_record_or_404(alloc["lotId"])
            if lot:
                lot["availableQty"] += alloc.get("allocatedQty", 0.0)
                lot["reservedQty"] = max(0.0, lot.get("reservedQty", 0.0) - alloc.get("allocatedQty", 0.0))
                postgres_sync.upsert_lot(lot)

        record["status"] = next_status
        postgres_sync.upsert_order(record)
        for alloc in allocations:
            alloc["status"] = AllocationStatus.cancelled.value
        postgres_sync.replace_allocations_for_order(order_id, allocations)
        store._allocations[order_id] = allocations
    events.emit(
        "order.cancelled",
        "Order",
        order_id,
        {"orderId": order_id, "reason": payload.reason if payload else None},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result
