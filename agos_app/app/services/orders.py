import copy
import uuid
from contextlib import nullcontext
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_order_code
from app.core.gateway import (
    assert_order_transition,
    check_idempotency,
    record_idempotency,
)
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.enums import AllocationStatus, LotStatus, OrderStatus, PaymentStatus, PreorderStatus
from app.models.orders import (
    AllocateOrderRequest,
    AllocationItemResponse,
    AllocationResponse,
    CancelOrderRequest,
    ConfirmOrderRequest,
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
from app.store._db import transaction as postgres_transaction


def _new_order_code() -> str:
    return generate_order_code()


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


def _emit_order_event(
    event_name: str,
    order_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Order",
        aggregate_id=order_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_order_decision(
    action_name: str,
    order_id: str,
    decision: str,
    context: dict[str, Any],
    *,
    before_snapshot: Any | None = None,
    after_snapshot: Any | None = None,
    reason_code: str | None = None,
    event: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    append_audit_decision(
        action_name=action_name,
        target_type="Order",
        target_id=order_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _raise_order_denied(
    *,
    action_name: str,
    order_id: str,
    context: dict[str, Any],
    detail: str,
    reason_code: str,
    status_code: int = 422,
    before_snapshot: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _audit_order_decision(
        action_name,
        order_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _recompute_preorder_remaining(record: dict[str, Any]) -> float:
    return float(max(
        Decimal("0"),
        Decimal(str(record.get("committedQty", 0.0) or 0.0))
        - Decimal(str(record.get("allocatedQty", 0.0) or 0.0))
        - Decimal(str(record.get("deliveredQty", 0.0) or 0.0))
        - Decimal(str(record.get("cancelledQty", 0.0) or 0.0)),
    ))


def _increment_preorder_allocated_qty(preorder_id: str, qty: float) -> None:
    preorder_record = postgres_sync.fetch_preorder(preorder_id) if postgres_sync.is_enabled() else store.get_preorder(preorder_id)
    if preorder_record is None:
        return

    if postgres_sync.is_enabled():
        updated_preorder = postgres_sync.increment_allocated_qty_atomic(preorder_id, qty)
        if updated_preorder is not None:
            store.save_preorder(preorder_id, updated_preorder)
        return

    updated_preorder = copy.deepcopy(preorder_record)
    updated_preorder["allocatedQty"] = float(updated_preorder.get("allocatedQty", 0.0) or 0.0) + qty
    updated_preorder["remainingQty"] = _recompute_preorder_remaining(updated_preorder)
    store.save_preorder(preorder_id, updated_preorder)


def _decrement_preorder_allocated_qty(preorder_id: str, qty: float) -> None:
    preorder_record = postgres_sync.fetch_preorder(preorder_id) if postgres_sync.is_enabled() else store.get_preorder(preorder_id)
    if preorder_record is None:
        return

    if postgres_sync.is_enabled():
        updated_preorder = postgres_sync.decrement_allocated_qty_atomic(preorder_id, qty)
        if updated_preorder is not None:
            store.save_preorder(preorder_id, updated_preorder)
        return

    updated_preorder = copy.deepcopy(preorder_record)
    updated_preorder["allocatedQty"] = max(0.0, float(updated_preorder.get("allocatedQty", 0.0) or 0.0) - qty)
    updated_preorder["remainingQty"] = _recompute_preorder_remaining(updated_preorder)
    store.save_preorder(preorder_id, updated_preorder)


def _record_preorder_delivery(
    preorder_id: str,
    qty: float,
    order_id: str,
    context: dict[str, Any],
) -> None:
    preorder_record = postgres_sync.fetch_preorder(preorder_id) if postgres_sync.is_enabled() else store.get_preorder(preorder_id)
    if preorder_record is None:
        return

    before_snapshot = copy.deepcopy(preorder_record)
    if postgres_sync.is_enabled():
        updated_preorder = postgres_sync.increment_preorder_delivered_qty_atomic(preorder_id, qty)
    else:
        updated_preorder = copy.deepcopy(preorder_record)
        updated_preorder["allocatedQty"] = max(0.0, float(updated_preorder.get("allocatedQty", 0.0) or 0.0) - qty)
        updated_preorder["deliveredQty"] = updated_preorder.get("deliveredQty", 0.0) + qty
        updated_preorder["remainingQty"] = _recompute_preorder_remaining(updated_preorder)
        completion_basis = (
            Decimal(str(updated_preorder.get("committedQty", 0.0) or 0.0))
            - Decimal(str(updated_preorder.get("deliveredQty", 0.0) or 0.0))
            - Decimal(str(updated_preorder.get("cancelledQty", 0.0) or 0.0))
        )
        if completion_basis <= Decimal("0"):
            updated_preorder["status"] = PreorderStatus.completed.value
        store.save_preorder(preorder_id, updated_preorder)

    if updated_preorder is None:
        return

    consumed_event = events.emit(
        event_name="preorder.quota_consumed",
        aggregate_type="Preorder",
        aggregate_id=preorder_id,
        payload={
            "preorderId": preorder_id,
            "orderId": order_id,
            "consumedQty": qty,
            "deliveredQty": updated_preorder["deliveredQty"],
            "remainingQty": updated_preorder["remainingQty"],
        },
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )

    completion_event = None
    if (
        before_snapshot.get("status") != PreorderStatus.completed.value
        and updated_preorder.get("status") == PreorderStatus.completed.value
    ):
        completion_event = events.emit(
            event_name="preorder.completed",
            aggregate_type="Preorder",
            aggregate_id=preorder_id,
            payload={
                "preorderId": preorder_id,
                "orderId": order_id,
                "finalDeliveredQty": updated_preorder["deliveredQty"],
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=consumed_event["eventId"],
            idempotency_key=context.get("idempotency_key"),
        )

    append_audit_decision(
        action_name="preorder.quota_consume",
        target_type="Preorder",
        target_id=preorder_id,
        decision="allowed",
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=updated_preorder,
        event=consumed_event,
        metadata={
            "orderId": order_id,
            "completionEventId": completion_event["eventId"] if completion_event else None,
        },
    )


def _get_order_record_or_404(
    order_id: str,
    *,
    action_name: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_order(order_id)
    else:
        record = store.get_order(order_id)

    if not record:
        if action_name and context is not None:
            _audit_order_decision(
                action_name,
                order_id,
                "denied",
                context,
                reason_code="order_not_found",
                metadata={"message": "Order not found."},
            )
        raise HTTPException(status_code=404, detail="Order not found.")
    return record


def _get_lot_record_or_404(lot_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        lot = postgres_sync.fetch_lot(lot_id)
    else:
        lot = store.get_lot(lot_id)

    if not lot:
        raise HTTPException(status_code=404, detail=f"Lot {lot_id} not found.")
    return lot


def _get_allocations_for_order(order_id: str) -> list[dict[str, Any]]:
    if postgres_sync.is_enabled():
        return postgres_sync.fetch_allocations_for_order(order_id)
    return store.get_allocations(order_id)


def create_order(payload: CreateOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    customer_exists = store.has_customer(payload.customerId)
    if postgres_sync.is_enabled():
        customer_exists = postgres_sync.customer_exists(payload.customerId)

    if not customer_exists:
        _raise_order_denied(
            action_name="order.create",
            order_id=f"pending:{payload.customerId}",
            context=context,
            detail="Customer not found.",
            reason_code="customer_not_found",
            status_code=404,
        )

    order_id = str(uuid.uuid4())
    order_code = _new_order_code()

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
        "tenantId": "default",
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
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            event_name="order.created",
            order_id=order_id,
            payload=record,
            context=context,
        )
        _audit_order_decision(
            "order.create",
            order_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.create",
            request_hash=build_request_hash(payload, extra={"action": "order.create"}),
        )

    if not postgres_sync.is_enabled():
        store.save_order(order_id, record)
    return result


def get_order(order_id: str) -> OrderDetail:
    record = _get_order_record_or_404(order_id)
    return _build_order_detail(record)


def confirm_order(order_id: str, payload: ConfirmOrderRequest | None = None) -> OrderResponse:
    context = meta_context(payload.meta if payload else None)
    record = _get_order_record_or_404(order_id, action_name="order.confirm", context=context)
    before_snapshot = copy.deepcopy(record)
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "confirm")
    except HTTPException as exc:
        _audit_order_decision(
            "order.confirm",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    record["status"] = next_status
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            "order.confirmed",
            order_id,
            {"orderId": order_id, "status": next_status},
            context,
        )
        _audit_order_decision(
            "order.confirm",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.confirm",
            request_hash=build_request_hash(payload or {}, extra={"action": "order.confirm", "orderId": order_id}),
        )
    return result


def allocate_order(order_id: str, payload: AllocateOrderRequest) -> AllocationResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.allocate", context=context)
    before_snapshot = copy.deepcopy(record)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return AllocationResponse(**cached)

    try:
        next_status = assert_order_transition(record, "allocate")
    except HTTPException as exc:
        _audit_order_decision(
            "order.allocate",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    existing_allocations = _get_allocations_for_order(order_id)
    all_allocations = list(existing_allocations)
    new_allocations: list[dict[str, Any]] = []
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
    preorder_allocations: list[tuple[str, float]] = []

    for item in payload.allocations:
        try:
            lot = _get_lot_record_or_404(item.lotId)
        except HTTPException as exc:
            if exc.status_code == 404:
                _raise_order_denied(
                    action_name="order.allocate",
                    order_id=order_id,
                    context=context,
                    detail=str(exc.detail),
                    reason_code="lot_not_found",
                    status_code=404,
                    before_snapshot=before_snapshot,
                    metadata={"lotId": item.lotId},
                )
            raise
        if lot["status"] != LotStatus.released.value:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"Lot {item.lotId} is not in released state (current: {lot['status']}).",
                reason_code="lot_not_released",
                before_snapshot=before_snapshot,
            )
        if lot["availableQty"] < item.allocatedQty:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"Lot {item.lotId} has insufficient available qty ({lot['availableQty']}).",
                reason_code="insufficient_lot_qty",
                before_snapshot=before_snapshot,
            )
        if item.orderLineId not in line_map:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"OrderLine {item.orderLineId} not found.",
                reason_code="order_line_not_found",
                before_snapshot=before_snapshot,
            )

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

        source_preorder_id = line_map[item.orderLineId].get("sourcePreorderId")
        if source_preorder_id:
            preorder_allocations.append((source_preorder_id, item.allocatedQty))

        if not postgres_sync.is_enabled():
            if source_preorder_id:
                _increment_preorder_allocated_qty(source_preorder_id, item.allocatedQty)
            lot["availableQty"] -= item.allocatedQty
            lot["reservedQty"] = lot.get("reservedQty", 0.0) + item.allocatedQty

    result = AllocationResponse(
        orderId=order_id,
        allocations=[AllocationItemResponse(**a) for a in new_allocations],
    )
    if postgres_sync.is_enabled():
        with postgres_transaction():
            try:
                postgres_sync.allocate_order_atomic(order_id, next_status, new_allocations)
            except ValueError as exc:
                _raise_order_denied(
                    action_name="order.allocate",
                    order_id=order_id,
                    context=context,
                    detail=str(exc),
                    reason_code="allocation_atomic_rejected",
                    before_snapshot=before_snapshot,
                )
            for source_preorder_id, allocated_qty in preorder_allocations:
                _increment_preorder_allocated_qty(source_preorder_id, allocated_qty)
            record = _get_order_record_or_404(order_id)
            event = _emit_order_event(
                "order.allocated",
                order_id,
                {"orderId": order_id, "allocations": new_allocations},
                context,
            )
            _audit_order_decision(
                "order.allocate",
                order_id,
                "allowed",
                context,
                before_snapshot=before_snapshot,
                after_snapshot=record,
                event=event,
                metadata={"allocationCount": len(new_allocations)},
            )
            record_idempotency(
                key,
                result.model_dump(),
                operation_name="order.allocate",
                request_hash=build_request_hash(payload, extra={"action": "order.allocate", "orderId": order_id}),
            )
    else:
        record["status"] = next_status
        postgres_sync.upsert_order(record)
        store.save_allocations(order_id, all_allocations)
        event = _emit_order_event(
            "order.allocated",
            order_id,
            {"orderId": order_id, "allocations": new_allocations},
            context,
        )
        _audit_order_decision(
            "order.allocate",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"allocationCount": len(new_allocations)},
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.allocate",
            request_hash=build_request_hash(payload, extra={"action": "order.allocate", "orderId": order_id}),
        )
    return result


def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.pack", context=context)
    before_snapshot = copy.deepcopy(record)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "pack")
    except HTTPException as exc:
        _audit_order_decision(
            "order.pack",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}

    for item in payload.packedQtySummary:
        if item.orderLineId not in line_map:
            _raise_order_denied(
                action_name="order.pack",
                order_id=order_id,
                context=context,
                detail=f"OrderLine {item.orderLineId} not found.",
                reason_code="order_line_not_found",
                before_snapshot=before_snapshot,
            )
        line_map[item.orderLineId]["packedQty"] = item.packedQty

    record["status"] = next_status
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event("order.packed", order_id, {"orderId": order_id, "status": next_status}, context)
        _audit_order_decision(
            "order.pack",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.pack",
            request_hash=build_request_hash(payload, extra={"action": "order.pack", "orderId": order_id}),
        )
    return result


def ship_order(order_id: str, payload: ShipOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.ship", context=context)
    before_snapshot = copy.deepcopy(record)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "ship")
    except HTTPException as exc:
        _audit_order_decision(
            "order.ship",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    record["status"] = next_status
    record["carrier"] = payload.carrier
    record["trackingRef"] = payload.trackingRef
    record["shippedAt"] = payload.shippedAt
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            "order.shipped",
            order_id,
            {"orderId": order_id, "carrier": payload.carrier, "trackingRef": payload.trackingRef},
            context,
        )
        _audit_order_decision(
            "order.ship",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.ship",
            request_hash=build_request_hash(payload, extra={"action": "order.ship", "orderId": order_id}),
        )
    return result


def deliver_order(order_id: str, payload: DeliverOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.deliver", context=context)
    before_snapshot = copy.deepcopy(record)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "deliver")
    except HTTPException as exc:
        _audit_order_decision(
            "order.deliver",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    record["status"] = next_status
    record["deliveredAt"] = payload.deliveredAt
    record["proofRef"] = payload.proofRef
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        for line in record["lines"]:
            if line.get("sourcePreorderId"):
                qty = line.get("deliveredQty", 0.0) or line.get("allocatedQty", 0.0)
                _record_preorder_delivery(line["sourcePreorderId"], qty, order_id, context)
        event = _emit_order_event(
            "order.delivered",
            order_id,
            {"orderId": order_id, "deliveredAt": payload.deliveredAt},
            context,
        )
        _audit_order_decision(
            "order.deliver",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.deliver",
            request_hash=build_request_hash(payload, extra={"action": "order.deliver", "orderId": order_id}),
        )
    return result


def request_cancel_order(order_id: str, payload: RequestCancelOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.request_cancel", context=context)
    before_snapshot = copy.deepcopy(record)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "request_cancel")
    except HTTPException as exc:
        _audit_order_decision(
            "order.request_cancel",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    record["status"] = next_status
    record["cancelReason"] = payload.reason
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            "order.cancel_requested",
            order_id,
            {"orderId": order_id, "reason": payload.reason},
            context,
        )
        _audit_order_decision(
            "order.request_cancel",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.request_cancel",
            request_hash=build_request_hash(payload, extra={"action": "order.request_cancel", "orderId": order_id}),
        )
    return result


def cancel_order(order_id: str, payload: CancelOrderRequest | None) -> OrderResponse:
    meta = payload.meta if payload else None
    context = meta_context(meta)
    record = _get_order_record_or_404(order_id, action_name="order.cancel", context=context)
    before_snapshot = copy.deepcopy(record)
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        next_status = assert_order_transition(record, "cancel")
    except HTTPException as exc:
        _audit_order_decision(
            "order.cancel",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    allocations = _get_allocations_for_order(order_id)
    preorder_by_line_id = {line["orderLineId"]: line.get("sourcePreorderId") for line in record.get("lines", [])}

    # Release reserved inventory back to lots
    result = OrderResponse(data=_build_order_detail(record))
    if postgres_sync.is_enabled():
        with postgres_transaction():
            postgres_sync.cancel_order_atomic(order_id, next_status)
            record = _get_order_record_or_404(order_id)
            allocations = _get_allocations_for_order(order_id)
            for alloc in allocations:
                source_preorder_id = preorder_by_line_id.get(alloc.get("orderLineId"))
                if source_preorder_id:
                    _decrement_preorder_allocated_qty(source_preorder_id, alloc.get("allocatedQty", 0.0))
            event = _emit_order_event(
                "order.cancelled",
                order_id,
                {"orderId": order_id, "reason": payload.reason if payload else None},
                context,
            )
            _audit_order_decision(
                "order.cancel",
                order_id,
                "allowed",
                context,
                before_snapshot=before_snapshot,
                after_snapshot=record,
                event=event,
            )
            record_idempotency(
                key,
                result.model_dump(),
                operation_name="order.cancel",
                request_hash=build_request_hash(payload or {}, extra={"action": "order.cancel", "orderId": order_id}),
            )
    else:
        for alloc in allocations:
            lot = _get_lot_record_or_404(alloc["lotId"])
            if lot:
                lot["availableQty"] += alloc.get("allocatedQty", 0.0)
                lot["reservedQty"] = max(0.0, lot.get("reservedQty", 0.0) - alloc.get("allocatedQty", 0.0))
                postgres_sync.upsert_lot(lot)
            source_preorder_id = preorder_by_line_id.get(alloc.get("orderLineId"))
            if source_preorder_id:
                _decrement_preorder_allocated_qty(source_preorder_id, alloc.get("allocatedQty", 0.0))

        record["status"] = next_status
        postgres_sync.upsert_order(record)
        for alloc in allocations:
            alloc["status"] = AllocationStatus.cancelled.value
        postgres_sync.replace_allocations_for_order(order_id, allocations)
        store.save_allocations(order_id, allocations)
        event = _emit_order_event(
            "order.cancelled",
            order_id,
            {"orderId": order_id, "reason": payload.reason if payload else None},
            context,
        )
        _audit_order_decision(
            "order.cancel",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="order.cancel",
            request_hash=build_request_hash(payload or {}, extra={"action": "order.cancel", "orderId": order_id}),
        )
    return result
