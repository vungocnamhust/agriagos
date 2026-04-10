import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.gateway import (
    assert_order_transition,
    check_idempotency,
    record_idempotency,
)
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


def create_order(payload: CreateOrderRequest) -> OrderResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    if payload.customerId not in store._customers:
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
        "status": "pending",
        "paymentStatus": "unpaid",
        "deliveryDateExpected": payload.deliveryDateExpected,
        "shippingAddress": payload.shippingAddress,
        "paymentIntent": payload.paymentIntent,
        "note": payload.note,
        "lines": lines,
    }
    store._orders[order_id] = record

    events.emit(
        event_name="OrderCreated",
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
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")
    return _build_order_detail(record)


def confirm_order(order_id: str) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    next_status = assert_order_transition(record, "confirm")
    record["status"] = next_status
    events.emit("OrderConfirmed", "Order", order_id, {"orderId": order_id, "status": next_status})
    return OrderResponse(data=_build_order_detail(record))


def allocate_order(order_id: str, payload: AllocateOrderRequest) -> AllocationResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return AllocationResponse(**cached)

    next_status = assert_order_transition(record, "allocate")

    allocation_records: list[dict[str, Any]] = []
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}

    for item in payload.allocations:
        lot = store._lots.get(item.lotId)
        if not lot:
            raise HTTPException(status_code=404, detail=f"Lot {item.lotId} not found.")
        if lot["status"] != "released":
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
        lot["availableQty"] -= item.allocatedQty
        lot["reservedQty"] = lot.get("reservedQty", 0.0) + item.allocatedQty
        line_map[item.orderLineId]["allocatedQty"] += item.allocatedQty

        allocation_id = str(uuid.uuid4())
        alloc_record = {
            "allocationId": allocation_id,
            "orderLineId": item.orderLineId,
            "lotId": item.lotId,
            "allocatedQty": item.allocatedQty,
            "status": "allocated",
        }
        allocation_records.append(alloc_record)
        store._allocations[order_id].append(alloc_record)

    record["status"] = next_status
    events.emit(
        "OrderAllocated",
        "Order",
        order_id,
        {"orderId": order_id, "allocations": allocation_records},
    )

    result = AllocationResponse(
        orderId=order_id,
        allocations=[AllocationItemResponse(**a) for a in allocation_records],
    )
    record_idempotency(key, result.model_dump())
    return result


def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

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
    events.emit("OrderPacked", "Order", order_id, {"orderId": order_id, "status": next_status})

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def ship_order(order_id: str, payload: ShipOrderRequest) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "ship")
    record["status"] = next_status
    record["carrier"] = payload.carrier
    record["trackingRef"] = payload.trackingRef
    record["shippedAt"] = payload.shippedAt

    events.emit(
        "OrderShipped",
        "Order",
        order_id,
        {"orderId": order_id, "carrier": payload.carrier, "trackingRef": payload.trackingRef},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def deliver_order(order_id: str, payload: DeliverOrderRequest) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "deliver")
    record["status"] = next_status
    record["deliveredAt"] = payload.deliveredAt
    record["proofRef"] = payload.proofRef

    # Consume preorder delivered qty for any lines linked to a preorder
    for line in record["lines"]:
        if line.get("sourcePreorderId"):
            preorder = store._preorders.get(line["sourcePreorderId"])
            if preorder:
                qty = line.get("deliveredQty", 0.0) or line.get("allocatedQty", 0.0)
                preorder["deliveredQty"] = preorder.get("deliveredQty", 0.0) + qty
                preorder["remainingQty"] = max(
                    0.0,
                    preorder["committedQty"] - preorder["deliveredQty"],
                )
                if preorder["remainingQty"] == 0:
                    preorder["status"] = "fulfilled"

    events.emit(
        "OrderDelivered",
        "Order",
        order_id,
        {"orderId": order_id, "deliveredAt": payload.deliveredAt},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def request_cancel_order(order_id: str, payload: RequestCancelOrderRequest) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "request_cancel")
    record["status"] = next_status
    record["cancelReason"] = payload.reason

    events.emit(
        "OrderCancelRequested",
        "Order",
        order_id,
        {"orderId": order_id, "reason": payload.reason},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def cancel_order(order_id: str, payload: CancelOrderRequest | None) -> OrderResponse:
    record = store._orders.get(order_id)
    if not record:
        raise HTTPException(status_code=404, detail="Order not found.")

    meta = payload.meta if payload else None
    key = meta.idempotencyKey if meta else None
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    next_status = assert_order_transition(record, "cancel")

    # Release reserved inventory back to lots
    for alloc in store._allocations.get(order_id, []):
        lot = store._lots.get(alloc["lotId"])
        if lot:
            lot["availableQty"] += alloc.get("allocatedQty", 0.0)
            lot["reservedQty"] = max(0.0, lot.get("reservedQty", 0.0) - alloc.get("allocatedQty", 0.0))

    record["status"] = next_status
    events.emit(
        "OrderCancelled",
        "Order",
        order_id,
        {"orderId": order_id, "reason": payload.reason if payload else None},
    )

    result = OrderResponse(data=_build_order_detail(record))
    record_idempotency(key, result.model_dump())
    return result
