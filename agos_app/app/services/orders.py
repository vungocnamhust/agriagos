import copy
import threading
import uuid
from contextlib import nullcontext
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_order_code
from app.core.gateway import (
    assert_order_transition,
    assert_order_transition_outcome,
    check_idempotency,
    record_idempotency,
)
from app.core.write_context import build_request_hash, meta_context
from app.models.common import Meta
from app.models.enums import AllocationStatus, LotStatus, OrderStatus, PaymentStatus, PreorderStatus
from app.models.orders import (
    AllocateOrderRequest,
    AdjustAllocationRequest,
    AllocationMutationResponse,
    AllocationItemResponse,
    AllocationResponse,
    CancelOrderRequest,
    ConfirmOrderRequest,
    CreateOrderRequest,
    DeliverOrderRequest,
    FailDeliveryRequest,
    OrderDetail,
    OrderLine,
    OrderResponse,
    PackOrderRequest,
    ReleaseAllocationRequest,
    RequestCancelOrderRequest,
    ShipOrderRequest,
)
from app.models.project_assignments import ProjectAssignmentSummary
from app.services import audit as audit_service
from app.store import postgres_sync
from app.store import memory as store
from app.store import organizations as organization_store
from app.store import project_assignments as project_assignment_store
from app.store._db import transaction as postgres_transaction


_MEMORY_ALLOCATION_LOCK = threading.RLock()

_ORDER_READ_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh", "ops", "accountant"})
_ORDER_CUSTOMER_WRITE_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh"})
_ORDER_OPS_WRITE_ROLES = frozenset({"founder", "super_admin", "admin", "ops"})
_ORDER_REQUEST_CANCEL_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh", "ops"})
_ORDER_STANDARD_CANCEL_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh", "ops"})
_ORDER_SENSITIVE_CANCEL_ROLES = frozenset({"founder", "super_admin", "admin", "ops"})
_SENSITIVE_CANCEL_STATUSES = frozenset(
    {
        OrderStatus.packed.value,
        OrderStatus.partially_packed.value,
        OrderStatus.shipped.value,
        OrderStatus.partially_delivered.value,
        OrderStatus.delivered.value,
        OrderStatus.failed.value,
    }
)


def _new_order_code() -> str:
    return generate_order_code()


def _effective_order_actor_role(context: dict[str, Any], *, allow_delegated_agent: bool = False) -> str | None:
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role != "agent" or not allow_delegated_agent:
        return actor_role

    delegated_actor_role = normalize_actor_role(context.get("delegated_actor_role"))
    return delegated_actor_role or actor_role


def _assert_order_access(
    *,
    context: dict[str, Any],
    action_name: str,
    order_id: str,
    allowed_roles: frozenset[str],
    reason_code: str,
    detail: str,
    before_snapshot: Any | None = None,
    allow_delegated_agent: bool = False,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="Order",
        target_id=order_id,
        context=context,
    )

    actor_role = _effective_order_actor_role(context, allow_delegated_agent=allow_delegated_agent)
    if actor_role in allowed_roles:
        return

    _audit_order_decision(
        action_name,
        order_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, "effectiveActorRole": actor_role},
    )
    raise HTTPException(status_code=403, detail=detail)


def _cancel_roles_for_status(order_status: str | None) -> frozenset[str]:
    if order_status in _SENSITIVE_CANCEL_STATUSES:
        return _ORDER_SENSITIVE_CANCEL_ROLES
    return _ORDER_STANDARD_CANCEL_ROLES


def _build_order_detail(record: dict[str, Any]) -> OrderDetail:
    lines = [OrderLine(**ln) for ln in record.get("lines", [])]
    assignments = _list_assignment_summaries("order", record["orderId"])
    return OrderDetail(
        orderId=record["orderId"],
        orderCode=record["orderCode"],
        organizationId=record.get("organizationId"),
        customerId=record["customerId"],
        orderDate=record.get("orderDate"),
        channel=record["channel"],
        status=record["status"],
        paymentStatus=record["paymentStatus"],
        deliveryDateExpected=record.get("deliveryDateExpected"),
        shippingAddress=record.get("shippingAddress"),
        carrier=record.get("carrier"),
        trackingRef=record.get("trackingRef"),
        shippedAt=record.get("shippedAt"),
        deliveredAt=record.get("deliveredAt"),
        proofRef=record.get("proofRef"),
        failureReason=record.get("failureReason"),
        note=record.get("note"),
        createdBy=record.get("createdBy"),
        sourcePreorderFlag=bool(record.get("sourcePreorderFlag", False)),
        version=int(record.get("version", 1) or 1),
        lines=lines,
        assignments=assignments,
    )


def _list_assignment_summaries(target_type: str, target_id: str) -> list[ProjectAssignmentSummary]:
    records = (
        project_assignment_store.list_project_assignments_for_target(target_type, target_id)
        if postgres_sync.is_enabled()
        else store.list_project_assignments_for_target(target_type, target_id)
    )
    return [ProjectAssignmentSummary(**record) for record in records]


def _linked_preorder_ids(lines: list[dict[str, Any]]) -> list[str]:
    if not lines:
        return []
    seen: set[str] = set()
    linked_ids: list[str] = []
    for line in lines:
        source_preorder_id = line.get("sourcePreorderId")
        if source_preorder_id and source_preorder_id not in seen:
            seen.add(source_preorder_id)
            linked_ids.append(source_preorder_id)
    return linked_ids


def _get_preorder_record(preorder_id: str) -> dict[str, Any] | None:
    if postgres_sync.is_enabled():
        return postgres_sync.fetch_preorder(preorder_id)
    return store.get_preorder(preorder_id)


def _organization_exists(organization_id: str) -> bool:
    if postgres_sync.is_enabled():
        return organization_store.organization_exists(organization_id)
    return store.get_organization(organization_id) is not None


def _validate_organization_id(organization_id: str | None) -> str | None:
    if organization_id is None:
        return None
    normalized = organization_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="organizationId cannot be blank.")
    if not _organization_exists(normalized):
        raise HTTPException(status_code=422, detail="Referenced organization was not found.")
    return normalized


def _resolve_order_organization_id(
    requested_organization_id: str | None,
    linked_preorder_ids: list[str],
    context: dict[str, Any],
    pending_order_id: str,
) -> str | None:
    validated_requested_id = _validate_organization_id(requested_organization_id)
    if not linked_preorder_ids:
        return validated_requested_id

    linked_org_ids: set[str] = set()
    for preorder_id in linked_preorder_ids:
        preorder_record = _get_preorder_record(preorder_id)
        if preorder_record is None:
            _raise_order_denied(
                action_name="order.create",
                order_id=pending_order_id,
                context=context,
                detail=f"Preorder {preorder_id} not found.",
                reason_code="source_preorder_not_found",
                status_code=404,
                metadata={"sourcePreorderId": preorder_id},
            )
        preorder_org_id = preorder_record.get("organizationId")
        if preorder_org_id is not None:
            linked_org_ids.add(str(preorder_org_id))

    if len(linked_org_ids) > 1:
        _raise_order_denied(
            action_name="order.create",
            order_id=pending_order_id,
            context=context,
            detail="Linked preorders must belong to the same organization.",
            reason_code="source_preorder_organization_conflict",
            status_code=422,
            metadata={"linkedPreorderIds": linked_preorder_ids},
        )

    if not linked_org_ids:
        return validated_requested_id

    linked_org_id = next(iter(linked_org_ids))
    if validated_requested_id is not None and validated_requested_id != linked_org_id:
        _raise_order_denied(
            action_name="order.create",
            order_id=pending_order_id,
            context=context,
            detail="Requested organizationId does not match linked preorder organization.",
            reason_code="organization_mismatch",
            status_code=422,
            metadata={"requestedOrganizationId": validated_requested_id, "linkedOrganizationId": linked_org_id},
        )

    return linked_org_id


def _validate_source_preorder_ids(lines: list[dict[str, Any]], context: dict[str, Any], order_id: str) -> None:
    allowed_statuses = {PreorderStatus.confirmed.value, PreorderStatus.active.value}
    for source_preorder_id in _linked_preorder_ids(lines):
        preorder_record = _get_preorder_record(source_preorder_id)
        if preorder_record is None:
            _raise_order_denied(
                action_name="order.create",
                order_id=order_id,
                context=context,
                detail=f"Preorder {source_preorder_id} not found.",
                reason_code="source_preorder_not_found",
                status_code=404,
                metadata={"sourcePreorderId": source_preorder_id},
            )
        assert preorder_record is not None
        preorder_status = preorder_record.get("status")
        if preorder_status not in allowed_statuses:
            _raise_order_denied(
                action_name="order.create",
                order_id=order_id,
                context=context,
                detail=(
                    f"Preorder {source_preorder_id} is not linkable from status {preorder_status}."
                ),
                reason_code="source_preorder_not_linkable",
                status_code=422,
                metadata={
                    "sourcePreorderId": source_preorder_id,
                    "preorderStatus": preorder_status,
                },
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


def _emit_allocation_event(
    event_name: str,
    allocation_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Allocation",
        aggregate_id=allocation_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _record_inventory_movement(
    *,
    lot_id: str,
    movement_type: str,
    qty: float,
    order_id: str,
    order_line_id: str,
    reason: str,
) -> None:
    movement = {
        "lotId": lot_id,
        "movementType": movement_type,
        "qty": qty,
        "relatedOrderId": order_id,
        "relatedOrderLineId": order_line_id,
        "reason": reason,
    }
    if postgres_sync.is_enabled():
        postgres_sync.append_inventory_movement(movement)
    else:
        store.append_inventory_movement(movement)


def _derive_order_allocation_status(lines: list[dict[str, Any]]) -> str:
    if not lines:
        return OrderStatus.confirmed.value

    has_any_allocation = False
    is_fully_allocated = True
    for line in lines:
        ordered_qty = _float_value(line.get("orderedQty"))
        allocated_qty = _float_value(line.get("allocatedQty"))
        if allocated_qty > 0:
            has_any_allocation = True
        if allocated_qty < ordered_qty:
            is_fully_allocated = False

    if not has_any_allocation:
        return OrderStatus.confirmed.value
    if is_fully_allocated:
        return OrderStatus.allocated.value
    return OrderStatus.partially_allocated.value


def _derive_order_pack_status(lines: list[dict[str, Any]]) -> str:
    if not lines:
        return OrderStatus.allocated.value

    has_any_packed_qty = False
    is_fully_packed = True
    for line in lines:
        ordered_qty = _float_value(line.get("orderedQty"))
        allocated_qty = _float_value(line.get("allocatedQty"))
        packed_qty = _float_value(line.get("packedQty"))
        if packed_qty > 0:
            has_any_packed_qty = True
        if allocated_qty > packed_qty or allocated_qty < ordered_qty:
            is_fully_packed = False

    if has_any_packed_qty and is_fully_packed:
        return OrderStatus.packed.value
    return OrderStatus.partially_packed.value


def _derive_order_delivery_status(lines: list[dict[str, Any]]) -> str:
    if not lines:
        return OrderStatus.delivered.value

    has_any_delivered_qty = False
    is_fully_delivered = True
    for line in lines:
        packed_qty = _float_value(line.get("packedQty"))
        delivered_qty = _float_value(line.get("deliveredQty"))
        if delivered_qty > 0:
            has_any_delivered_qty = True
        if delivered_qty < packed_qty:
            is_fully_delivered = False

    if has_any_delivered_qty and is_fully_delivered:
        return OrderStatus.delivered.value
    return OrderStatus.partially_delivered.value


def _update_customer_last_purchase(
    customer_id: str,
    order_id: str,
    delivered_at: str | None,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    customer_record = postgres_sync.fetch_customer(customer_id) if postgres_sync.is_enabled() else store.get_customer(customer_id)
    if customer_record is None:
        return None

    updated_customer = copy.deepcopy(customer_record)
    updated_customer["lastOrderAt"] = delivered_at or store.now_iso()

    if postgres_sync.is_enabled():
        postgres_sync.upsert_customer(updated_customer)
    else:
        store.save_customer(customer_id, updated_customer)

    return events.emit(
        event_name="customer.last_purchase_updated",
        aggregate_type="Customer",
        aggregate_id=customer_id,
        payload={
            "customerId": customer_id,
            "lastOrderId": order_id,
            "lastPurchaseAt": updated_customer["lastOrderAt"],
        },
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _allocation_order_event_name(order_status: str) -> str:
    if order_status == OrderStatus.partially_allocated.value:
        return "order.partially_allocated"
    return "order.allocated"


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
    audit_service.append_domain_audit_decision(
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


def _float_value(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _collect_allocation_request_totals(
    allocations: list[Any],
) -> tuple[dict[str, float], dict[str, float]]:
    lot_totals: dict[str, float] = {}
    line_totals: dict[str, float] = {}

    for item in allocations:
        lot_totals[item.lotId] = lot_totals.get(item.lotId, 0.0) + _float_value(item.allocatedQty)
        line_totals[item.orderLineId] = line_totals.get(item.orderLineId, 0.0) + _float_value(item.allocatedQty)

    return lot_totals, line_totals


def _validate_allocation_request(
    *,
    order_id: str,
    allocations: list[Any],
    line_map: dict[str, dict[str, Any]],
    context: dict[str, Any],
    before_snapshot: Any,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    lot_totals, line_totals = _collect_allocation_request_totals(allocations)

    lots_by_id: dict[str, dict[str, Any]] = {}
    for lot_id, requested_qty in lot_totals.items():
        try:
            lot = _get_lot_record_or_404(lot_id)
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
                    metadata={"lotId": lot_id},
                )
            raise

        if lot["status"] != LotStatus.released.value:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"Lot {lot_id} is not in released state (current: {lot['status']}).",
                reason_code="lot_not_released",
                before_snapshot=before_snapshot,
            )

        if _float_value(lot.get("availableQty")) < requested_qty:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"Lot {lot_id} has insufficient available qty ({lot['availableQty']}).",
                reason_code="insufficient_lot_qty",
                before_snapshot=before_snapshot,
                metadata={"lotId": lot_id, "requestedQty": requested_qty},
            )

        lots_by_id[lot_id] = lot

    preorder_records: dict[str, dict[str, Any]] = {}
    for order_line_id, requested_qty in line_totals.items():
        if order_line_id not in line_map:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=f"OrderLine {order_line_id} not found.",
                reason_code="order_line_not_found",
                before_snapshot=before_snapshot,
            )

        line = line_map[order_line_id]
        remaining_line_qty = _float_value(line.get("orderedQty")) - _float_value(line.get("allocatedQty"))
        if requested_qty > remaining_line_qty:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=(
                    f"OrderLine {order_line_id} allocation exceeds remaining qty ({remaining_line_qty})."
                ),
                reason_code="order_line_qty_exceeded",
                before_snapshot=before_snapshot,
                metadata={"orderLineId": order_line_id, "requestedQty": requested_qty},
            )

        source_preorder_id = line.get("sourcePreorderId")
        if not source_preorder_id:
            continue

        preorder_record = preorder_records.get(source_preorder_id)
        if preorder_record is None:
            loaded_preorder_record = _get_preorder_record(source_preorder_id)
            if loaded_preorder_record is None:
                _raise_order_denied(
                    action_name="order.allocate",
                    order_id=order_id,
                    context=context,
                    detail=f"Preorder {source_preorder_id} not found.",
                    reason_code="preorder_not_found",
                    status_code=404,
                    before_snapshot=before_snapshot,
                    metadata={"sourcePreorderId": source_preorder_id},
                )
            preorder_record = loaded_preorder_record
            assert preorder_record is not None
            preorder_records[source_preorder_id] = preorder_record

        assert preorder_record is not None
        remaining_preorder_qty = _float_value(preorder_record.get("remainingQty"))
        if requested_qty > remaining_preorder_qty:
            _raise_order_denied(
                action_name="order.allocate",
                order_id=order_id,
                context=context,
                detail=(
                    f"Preorder {source_preorder_id} has insufficient remaining qty ({remaining_preorder_qty})."
                ),
                reason_code="preorder_quota_exceeded",
                before_snapshot=before_snapshot,
                metadata={"sourcePreorderId": source_preorder_id, "requestedQty": requested_qty},
            )

    return lots_by_id, preorder_records


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

    audit_service.append_domain_audit_decision(
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


def _get_allocation_for_order_or_404(order_id: str, allocation_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        allocation = postgres_sync.fetch_allocation_for_order(order_id, allocation_id)
    else:
        allocation = next(
            (item for item in store.get_allocations(order_id) if item["allocationId"] == allocation_id),
            None,
        )

    if allocation is None:
        raise HTTPException(status_code=404, detail=f"Allocation {allocation_id} not found.")
    return allocation


def create_order(payload: CreateOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    _assert_order_access(
        context=context,
        action_name="order.create",
        order_id=f"pending:{payload.customerId}",
        allowed_roles=_ORDER_CUSTOMER_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to create orders.",
    )
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

    _validate_source_preorder_ids(lines, context, f"pending:{payload.customerId}")
    linked_preorder_ids = _linked_preorder_ids(lines)
    organization_id = _resolve_order_organization_id(
        payload.organizationId,
        linked_preorder_ids,
        context,
        f"pending:{payload.customerId}",
    )

    record: dict[str, Any] = {
        "orderId": order_id,
        "tenantId": "default",
        "orderCode": order_code,
        "organizationId": organization_id,
        "customerId": payload.customerId,
        "channel": payload.channel,
        "status": OrderStatus.draft.value,
        "paymentStatus": PaymentStatus.unpaid.value,
        "deliveryDateExpected": payload.deliveryDateExpected,
        "shippingAddress": payload.shippingAddress,
        "paymentIntent": payload.paymentIntent,
        "note": payload.note,
        "sourcePreorderFlag": bool(linked_preorder_ids),
        "lines": lines,
    }
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            event_name="order.created",
            order_id=order_id,
            payload={
                **record,
                "linkedPreorderIds": linked_preorder_ids,
            },
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


def get_order(order_id: str, meta: Meta | None = None) -> OrderDetail:
    context = meta_context(meta)
    _assert_order_access(
        context=context,
        action_name="order.get",
        order_id=order_id,
        allowed_roles=_ORDER_READ_ROLES,
        reason_code="forbidden_order_read",
        detail="Actor is not allowed to read order details.",
    )
    record = _get_order_record_or_404(order_id)
    return _build_order_detail(record)


def confirm_order(order_id: str, payload: ConfirmOrderRequest | None = None) -> OrderResponse:
    context = meta_context(payload.meta if payload else None)
    record = _get_order_record_or_404(order_id, action_name="order.confirm", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="order.confirm",
        order_id=order_id,
        allowed_roles=_ORDER_CUSTOMER_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to confirm orders.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    _validate_source_preorder_ids(record.get("lines", []), context, order_id)

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
    linked_preorder_ids = _linked_preorder_ids(record.get("lines", []))
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            "order.confirmed",
            order_id,
            {
                "orderId": order_id,
                "status": next_status,
                "sourcePreorderFlag": bool(linked_preorder_ids),
                "linkedPreorderIds": linked_preorder_ids,
            },
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
    _assert_order_access(
        context=context,
        action_name="order.allocate",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to allocate orders.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return AllocationResponse(**cached)

    try:
        assert_order_transition(record, "allocate")
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

    if not postgres_sync.is_enabled():
        with _MEMORY_ALLOCATION_LOCK:
            record = _get_order_record_or_404(order_id, action_name="order.allocate", context=context)
            line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
            preview_lines = copy.deepcopy(record["lines"])
            preview_line_map = {ln["orderLineId"]: ln for ln in preview_lines}
            lots_by_id, _ = _validate_allocation_request(
                order_id=order_id,
                allocations=payload.allocations,
                line_map=line_map,
                context=context,
                before_snapshot=before_snapshot,
            )
            existing_allocations = _get_allocations_for_order(order_id)
            all_allocations = list(existing_allocations)
            new_allocations: list[dict[str, Any]] = []

            for item in payload.allocations:
                preview_line_map[item.orderLineId]["allocatedQty"] += item.allocatedQty

            next_status = _derive_order_allocation_status(preview_lines)
            try:
                assert_order_transition_outcome(record, "allocate", next_status)
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

            for item in payload.allocations:
                lot = lots_by_id[item.lotId]
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
                    _increment_preorder_allocated_qty(source_preorder_id, item.allocatedQty)
                lot["availableQty"] -= item.allocatedQty
                lot["reservedQty"] = lot.get("reservedQty", 0.0) + item.allocatedQty
                _record_inventory_movement(
                    lot_id=item.lotId,
                    movement_type="reserve",
                    qty=_float_value(item.allocatedQty),
                    order_id=order_id,
                    order_line_id=item.orderLineId,
                    reason="allocation_reserved",
                )

            result = AllocationResponse(
                orderId=order_id,
                allocations=[AllocationItemResponse(**a) for a in new_allocations],
            )
            record["status"] = next_status
            postgres_sync.upsert_order(record)
            store.save_allocations(order_id, all_allocations)
            event = _emit_order_event(
                _allocation_order_event_name(next_status),
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

    new_allocations: list[dict[str, Any]] = []
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
    lots_by_id, _ = _validate_allocation_request(
        order_id=order_id,
        allocations=payload.allocations,
        line_map=line_map,
        context=context,
        before_snapshot=before_snapshot,
    )

    for item in payload.allocations:
        line_map[item.orderLineId]["allocatedQty"] += item.allocatedQty
        allocation_id = str(uuid.uuid4())
        alloc_record = {
            "allocationId": allocation_id,
            "orderLineId": item.orderLineId,
            "lotId": item.lotId,
            "allocatedQty": item.allocatedQty,
            "status": AllocationStatus.active.value,
        }
        new_allocations.append(alloc_record)

    next_status = _derive_order_allocation_status(list(line_map.values()))
    try:
        assert_order_transition_outcome(record, "allocate", next_status)
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
            record = _get_order_record_or_404(order_id)
            event = _emit_order_event(
                _allocation_order_event_name(next_status),
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


def adjust_allocation(
    order_id: str,
    allocation_id: str,
    payload: AdjustAllocationRequest,
) -> AllocationMutationResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="allocation.adjust", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="allocation.adjust",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to adjust allocations.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return AllocationMutationResponse(**cached)

    if payload.newAllocatedQty <= 0:
        _raise_order_denied(
            action_name="allocation.adjust",
            order_id=order_id,
            context=context,
            detail="newAllocatedQty must be greater than 0. Use the release route to fully release an allocation.",
            reason_code="allocation_adjust_invalid_qty",
            before_snapshot=before_snapshot,
        )

    allocation = _get_allocation_for_order_or_404(order_id, allocation_id)
    if allocation["status"] != AllocationStatus.active.value:
        _raise_order_denied(
            action_name="allocation.adjust",
            order_id=order_id,
            context=context,
            detail=f"Allocation {allocation_id} is not adjustable from status {allocation['status']}.",
            reason_code="allocation_not_adjustable",
            before_snapshot=before_snapshot,
        )

    old_qty = _float_value(allocation.get("allocatedQty"))

    if postgres_sync.is_enabled():
        with postgres_transaction():
            try:
                updated_allocation, next_status = postgres_sync.adjust_allocation_atomic(
                    order_id,
                    allocation_id,
                    payload.newAllocatedQty,
                )
            except ValueError as exc:
                _raise_order_denied(
                    action_name="allocation.adjust",
                    order_id=order_id,
                    context=context,
                    detail=str(exc),
                    reason_code="allocation_adjust_rejected",
                    before_snapshot=before_snapshot,
                )
            else:
                order_status = OrderStatus(next_status)

                record = _get_order_record_or_404(order_id)
                event = _emit_allocation_event(
                    "allocation.adjusted",
                    allocation_id,
                    {
                        "allocationId": allocation_id,
                        "orderId": order_id,
                        "orderLineId": updated_allocation["orderLineId"],
                        "lotId": updated_allocation["lotId"],
                        "oldQty": old_qty,
                        "newQty": payload.newAllocatedQty,
                        "reason": payload.reason,
                        "approvalRef": payload.approvalRef,
                    },
                    context,
                )
                response = AllocationMutationResponse(
                    orderId=order_id,
                    orderStatus=order_status,
                    allocation=AllocationItemResponse(**updated_allocation),
                )
                _audit_order_decision(
                    "allocation.adjust",
                    order_id,
                    "allowed",
                    context,
                    before_snapshot=before_snapshot,
                    after_snapshot=record,
                    event=event,
                    metadata={"allocationId": allocation_id},
                )
                record_idempotency(
                    key,
                    response.model_dump(),
                    operation_name="allocation.adjust",
                    request_hash=build_request_hash(payload, extra={"action": "allocation.adjust", "orderId": order_id, "allocationId": allocation_id}),
                )
                return response

    with _MEMORY_ALLOCATION_LOCK:
        record = _get_order_record_or_404(order_id, action_name="allocation.adjust", context=context)
        allocations = _get_allocations_for_order(order_id)
        allocation = _get_allocation_for_order_or_404(order_id, allocation_id)
        old_qty = _float_value(allocation.get("allocatedQty"))
        delta = _float_value(payload.newAllocatedQty) - old_qty
        line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
        line = line_map[allocation["orderLineId"]]
        lot = _get_lot_record_or_404(allocation["lotId"])
        source_preorder_id = line.get("sourcePreorderId")

        if delta > 0:
            if lot["status"] != LotStatus.released.value:
                _raise_order_denied(
                    action_name="allocation.adjust",
                    order_id=order_id,
                    context=context,
                    detail=f"Lot {allocation['lotId']} is not in released state (current: {lot['status']}).",
                    reason_code="lot_not_released",
                    before_snapshot=before_snapshot,
                )
            if _float_value(lot.get("availableQty")) < delta:
                _raise_order_denied(
                    action_name="allocation.adjust",
                    order_id=order_id,
                    context=context,
                    detail=f"Lot {allocation['lotId']} has insufficient available qty ({lot['availableQty']}).",
                    reason_code="insufficient_lot_qty",
                    before_snapshot=before_snapshot,
                )
            remaining_line_qty = _float_value(line.get("orderedQty")) - _float_value(line.get("allocatedQty"))
            if delta > remaining_line_qty:
                _raise_order_denied(
                    action_name="allocation.adjust",
                    order_id=order_id,
                    context=context,
                    detail=f"OrderLine {allocation['orderLineId']} allocation exceeds remaining qty ({remaining_line_qty}).",
                    reason_code="order_line_qty_exceeded",
                    before_snapshot=before_snapshot,
                )
            if source_preorder_id:
                preorder_record = _get_preorder_record(source_preorder_id)
                if preorder_record is None:
                    _raise_order_denied(
                        action_name="allocation.adjust",
                        order_id=order_id,
                        context=context,
                        detail=f"Preorder {source_preorder_id} not found.",
                        reason_code="preorder_not_found",
                        status_code=404,
                        before_snapshot=before_snapshot,
                    )
                assert preorder_record is not None
                if _float_value(preorder_record.get("remainingQty")) < delta:
                    _raise_order_denied(
                        action_name="allocation.adjust",
                        order_id=order_id,
                        context=context,
                        detail=f"Preorder {source_preorder_id} has insufficient remaining qty ({preorder_record['remainingQty']}).",
                        reason_code="preorder_quota_exceeded",
                        before_snapshot=before_snapshot,
                    )
                _increment_preorder_allocated_qty(source_preorder_id, delta)

            line["allocatedQty"] += delta
            lot["availableQty"] -= delta
            lot["reservedQty"] = _float_value(lot.get("reservedQty")) + delta
            _record_inventory_movement(
                lot_id=allocation["lotId"],
                movement_type="reserve",
                qty=delta,
                order_id=order_id,
                order_line_id=allocation["orderLineId"],
                reason="allocation_adjusted_up",
            )
        elif delta < 0:
            release_qty = abs(delta)
            if source_preorder_id:
                _decrement_preorder_allocated_qty(source_preorder_id, release_qty)
            line["allocatedQty"] = max(0.0, _float_value(line.get("allocatedQty")) - release_qty)
            lot["availableQty"] += release_qty
            lot["reservedQty"] = max(0.0, _float_value(lot.get("reservedQty")) - release_qty)
            _record_inventory_movement(
                lot_id=allocation["lotId"],
                movement_type="release_reservation",
                qty=release_qty,
                order_id=order_id,
                order_line_id=allocation["orderLineId"],
                reason="allocation_adjusted_down",
            )

        allocation["allocatedQty"] = _float_value(payload.newAllocatedQty)
        next_status = OrderStatus(_derive_order_allocation_status(record["lines"]))
        record["status"] = next_status.value
        store.save_lot(allocation["lotId"], lot)
        store.save_order(order_id, record)
        store.save_allocations(order_id, allocations)
        event = _emit_allocation_event(
            "allocation.adjusted",
            allocation_id,
            {
                "allocationId": allocation_id,
                "orderId": order_id,
                "orderLineId": allocation["orderLineId"],
                "lotId": allocation["lotId"],
                "oldQty": old_qty,
                "newQty": payload.newAllocatedQty,
                "reason": payload.reason,
                "approvalRef": payload.approvalRef,
            },
            context,
        )
        response = AllocationMutationResponse(
            orderId=order_id,
            orderStatus=next_status,
            allocation=AllocationItemResponse(**allocation),
        )
        _audit_order_decision(
            "allocation.adjust",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"allocationId": allocation_id},
        )
        record_idempotency(
            key,
            response.model_dump(),
            operation_name="allocation.adjust",
            request_hash=build_request_hash(payload, extra={"action": "allocation.adjust", "orderId": order_id, "allocationId": allocation_id}),
        )
        return response


def release_allocation(
    order_id: str,
    allocation_id: str,
    payload: ReleaseAllocationRequest,
) -> AllocationMutationResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="allocation.release", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="allocation.release",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to release allocations.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return AllocationMutationResponse(**cached)

    allocation = _get_allocation_for_order_or_404(order_id, allocation_id)
    if allocation["status"] != AllocationStatus.active.value:
        _raise_order_denied(
            action_name="allocation.release",
            order_id=order_id,
            context=context,
            detail=f"Allocation {allocation_id} is not releasable from status {allocation['status']}.",
            reason_code="allocation_not_releasable",
            before_snapshot=before_snapshot,
        )

    release_qty = _float_value(allocation.get("allocatedQty"))

    if postgres_sync.is_enabled():
        with postgres_transaction():
            try:
                released_allocation, next_status = postgres_sync.release_allocation_atomic(order_id, allocation_id)
            except ValueError as exc:
                _raise_order_denied(
                    action_name="allocation.release",
                    order_id=order_id,
                    context=context,
                    detail=str(exc),
                    reason_code="allocation_release_rejected",
                    before_snapshot=before_snapshot,
                )
            else:
                order_status = OrderStatus(next_status)

                record = _get_order_record_or_404(order_id)
                event = _emit_allocation_event(
                    "allocation.released",
                    allocation_id,
                    {
                        "allocationId": allocation_id,
                        "orderId": order_id,
                        "orderLineId": released_allocation["orderLineId"],
                        "lotId": released_allocation["lotId"],
                        "releasedQty": release_qty,
                        "reason": payload.reason,
                        "approvalRef": payload.approvalRef,
                    },
                    context,
                )
                response = AllocationMutationResponse(
                    orderId=order_id,
                    orderStatus=order_status,
                    allocation=AllocationItemResponse(**released_allocation),
                )
                _audit_order_decision(
                    "allocation.release",
                    order_id,
                    "allowed",
                    context,
                    before_snapshot=before_snapshot,
                    after_snapshot=record,
                    event=event,
                    metadata={"allocationId": allocation_id},
                )
                record_idempotency(
                    key,
                    response.model_dump(),
                    operation_name="allocation.release",
                    request_hash=build_request_hash(payload, extra={"action": "allocation.release", "orderId": order_id, "allocationId": allocation_id}),
                )
                return response

    with _MEMORY_ALLOCATION_LOCK:
        record = _get_order_record_or_404(order_id, action_name="allocation.release", context=context)
        allocations = _get_allocations_for_order(order_id)
        allocation = _get_allocation_for_order_or_404(order_id, allocation_id)
        line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
        line = line_map[allocation["orderLineId"]]
        lot = _get_lot_record_or_404(allocation["lotId"])
        source_preorder_id = line.get("sourcePreorderId")

        if source_preorder_id:
            _decrement_preorder_allocated_qty(source_preorder_id, release_qty)
        line["allocatedQty"] = max(0.0, _float_value(line.get("allocatedQty")) - release_qty)
        lot["availableQty"] += release_qty
        lot["reservedQty"] = max(0.0, _float_value(lot.get("reservedQty")) - release_qty)
        allocation["status"] = AllocationStatus.released.value
        next_status = OrderStatus(_derive_order_allocation_status(record["lines"]))
        record["status"] = next_status.value
        store.save_lot(allocation["lotId"], lot)
        store.save_order(order_id, record)
        store.save_allocations(order_id, allocations)
        _record_inventory_movement(
            lot_id=allocation["lotId"],
            movement_type="release_reservation",
            qty=release_qty,
            order_id=order_id,
            order_line_id=allocation["orderLineId"],
            reason="allocation_released",
        )
        event = _emit_allocation_event(
            "allocation.released",
            allocation_id,
            {
                "allocationId": allocation_id,
                "orderId": order_id,
                "orderLineId": allocation["orderLineId"],
                "lotId": allocation["lotId"],
                "releasedQty": release_qty,
                "reason": payload.reason,
                "approvalRef": payload.approvalRef,
            },
            context,
        )
        response = AllocationMutationResponse(
            orderId=order_id,
            orderStatus=next_status,
            allocation=AllocationItemResponse(**allocation),
        )
        _audit_order_decision(
            "allocation.release",
            order_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"allocationId": allocation_id},
        )
        record_idempotency(
            key,
            response.model_dump(),
            operation_name="allocation.release",
            request_hash=build_request_hash(payload, extra={"action": "allocation.release", "orderId": order_id, "allocationId": allocation_id}),
        )
        return response


def pack_order(order_id: str, payload: PackOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.pack", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="order.pack",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to pack orders.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        assert_order_transition(record, "pack")
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
    preview_lines = copy.deepcopy(record["lines"])
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
    preview_line_map = {ln["orderLineId"]: ln for ln in preview_lines}

    for item in payload.packedQtySummary:
        if item.orderLineId not in preview_line_map:
            _raise_order_denied(
                action_name="order.pack",
                order_id=order_id,
                context=context,
                detail=f"OrderLine {item.orderLineId} not found.",
                reason_code="order_line_not_found",
                before_snapshot=before_snapshot,
            )
        allocated_qty = _float_value(preview_line_map[item.orderLineId].get("allocatedQty"))
        packed_qty = _float_value(item.packedQty)
        if packed_qty < 0 or packed_qty > allocated_qty:
            _raise_order_denied(
                action_name="order.pack",
                order_id=order_id,
                context=context,
                detail=(
                    f"OrderLine {item.orderLineId} packed qty must be between 0 and allocated qty ({allocated_qty})."
                ),
                reason_code="packed_qty_invalid",
                before_snapshot=before_snapshot,
                metadata={"orderLineId": item.orderLineId, "packedQty": packed_qty},
            )
        preview_line_map[item.orderLineId]["packedQty"] = item.packedQty
        preview_line_map[item.orderLineId]["status"] = (
            "packed" if packed_qty == allocated_qty and allocated_qty > 0 else line_map[item.orderLineId].get("status", "open")
        )

    next_status = _derive_order_pack_status(preview_lines)
    try:
        assert_order_transition_outcome(record, "pack", next_status)
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

    for item in payload.packedQtySummary:
        allocated_qty = _float_value(line_map[item.orderLineId].get("allocatedQty"))
        packed_qty = _float_value(item.packedQty)
        line_map[item.orderLineId]["packedQty"] = item.packedQty
        line_map[item.orderLineId]["status"] = (
            "packed" if packed_qty == allocated_qty and allocated_qty > 0 else line_map[item.orderLineId].get("status", "open")
        )
    record["status"] = next_status
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event_name = "order.packed" if next_status == OrderStatus.packed.value else "order.partially_packed"
        event = _emit_order_event(
            event_name,
            order_id,
            {
                "orderId": order_id,
                "status": next_status,
                "packedQtySummary": [
                    {
                        "orderLineId": line["orderLineId"],
                        "packedQty": _float_value(line.get("packedQty")),
                    }
                    for line in record["lines"]
                ],
            },
            context,
        )
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
    _assert_order_access(
        context=context,
        action_name="order.ship",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to ship orders.",
        before_snapshot=before_snapshot,
    )

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
    _assert_order_access(
        context=context,
        action_name="order.deliver",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to deliver orders.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    try:
        assert_order_transition(record, "deliver")
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

    preview_lines = copy.deepcopy(record["lines"])
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
    preview_line_map = {ln["orderLineId"]: ln for ln in preview_lines}
    delivered_delta_by_line_id: dict[str, float] = {}
    if payload.deliveredQtySummary:
        for item in payload.deliveredQtySummary:
            if item.orderLineId not in preview_line_map:
                _raise_order_denied(
                    action_name="order.deliver",
                    order_id=order_id,
                    context=context,
                    detail=f"OrderLine {item.orderLineId} not found.",
                    reason_code="order_line_not_found",
                    before_snapshot=before_snapshot,
                )
            line = preview_line_map[item.orderLineId]
            current_delivered_qty = _float_value(line.get("deliveredQty"))
            target_delivered_qty = _float_value(item.deliveredQty)
            packed_qty = _float_value(line.get("packedQty") or line.get("allocatedQty"))
            if target_delivered_qty < current_delivered_qty or target_delivered_qty > packed_qty:
                _raise_order_denied(
                    action_name="order.deliver",
                    order_id=order_id,
                    context=context,
                    detail=(
                        f"OrderLine {item.orderLineId} delivered qty must stay between current delivered qty ({current_delivered_qty}) and packed qty ({packed_qty})."
                    ),
                    reason_code="delivered_qty_invalid",
                    before_snapshot=before_snapshot,
                    metadata={"orderLineId": item.orderLineId, "deliveredQty": target_delivered_qty},
                )
            line["deliveredQty"] = target_delivered_qty
            line["status"] = "delivered" if target_delivered_qty == packed_qty and packed_qty > 0 else line.get("status", "packed")
            delivered_delta_by_line_id[item.orderLineId] = max(target_delivered_qty - current_delivered_qty, 0.0)
    else:
        for line in preview_lines:
            current_delivered_qty = _float_value(line.get("deliveredQty"))
            target_delivered_qty = _float_value(line.get("packedQty") or line.get("allocatedQty"))
            line["deliveredQty"] = target_delivered_qty
            line["status"] = "delivered" if target_delivered_qty > 0 else line.get("status", "packed")
            delivered_delta_by_line_id[line["orderLineId"]] = max(target_delivered_qty - current_delivered_qty, 0.0)

    next_status = _derive_order_delivery_status(preview_lines)
    try:
        assert_order_transition_outcome(record, "deliver", next_status)
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

    record["lines"] = preview_lines
    line_map = {ln["orderLineId"]: ln for ln in record["lines"]}
    delivered_deltas = [
        (line_map[line_id], delivered_delta)
        for line_id, delivered_delta in delivered_delta_by_line_id.items()
        if delivered_delta > 0
    ]
    record["status"] = next_status
    record["deliveredAt"] = payload.deliveredAt
    record["proofRef"] = payload.proofRef
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        for line, delivered_delta in delivered_deltas:
            if line.get("sourcePreorderId"):
                _record_preorder_delivery(line["sourcePreorderId"], delivered_delta, order_id, context)
        if delivered_deltas:
            _update_customer_last_purchase(record["customerId"], order_id, payload.deliveredAt, context)
        event_name = "order.delivered" if next_status == OrderStatus.delivered.value else "order.partially_delivered"
        event = _emit_order_event(
            event_name,
            order_id,
            {
                "orderId": order_id,
                "deliveredAt": payload.deliveredAt,
                "proofRef": payload.proofRef,
                "deliveredQtySummary": [
                    {
                        "orderLineId": line["orderLineId"],
                        "deliveredQty": _float_value(line.get("deliveredQty")),
                    }
                    for line in record["lines"]
                ],
            },
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


def fail_delivery(order_id: str, payload: FailDeliveryRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.fail_delivery", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="order.fail_delivery",
        order_id=order_id,
        allowed_roles=_ORDER_OPS_WRITE_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to mark delivery failures.",
        before_snapshot=before_snapshot,
    )
    normalized_failure_reason = payload.failureReason.strip()

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrderResponse(**cached)

    if not normalized_failure_reason:
        _raise_order_denied(
            action_name="order.fail_delivery",
            order_id=order_id,
            context=context,
            detail="failureReason is required when delivery fails.",
            reason_code="delivery_failure_reason_required",
            before_snapshot=before_snapshot,
        )

    try:
        next_status = assert_order_transition(record, "fail_delivery")
    except HTTPException as exc:
        _audit_order_decision(
            "order.fail_delivery",
            order_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    record["status"] = next_status
    record["deliveryNote"] = payload.note
    record["failureReason"] = normalized_failure_reason
    result = OrderResponse(data=_build_order_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_order(record)
        event = _emit_order_event(
            "order.delivery_failed",
            order_id,
            {
                "orderId": order_id,
                "reason": normalized_failure_reason,
                "note": payload.note,
            },
            context,
        )
        _audit_order_decision(
            "order.fail_delivery",
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
            operation_name="order.fail_delivery",
            request_hash=build_request_hash(payload, extra={"action": "order.fail_delivery", "orderId": order_id}),
        )
    return result


def request_cancel_order(order_id: str, payload: RequestCancelOrderRequest) -> OrderResponse:
    context = meta_context(payload.meta)
    record = _get_order_record_or_404(order_id, action_name="order.request_cancel", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_order_access(
        context=context,
        action_name="order.request_cancel",
        order_id=order_id,
        allowed_roles=_ORDER_REQUEST_CANCEL_ROLES,
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to request order cancellation.",
        before_snapshot=before_snapshot,
    )

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
    _assert_order_access(
        context=context,
        action_name="order.cancel",
        order_id=order_id,
        allowed_roles=_cancel_roles_for_status(record.get("status")),
        reason_code="forbidden_order_write",
        detail="Actor is not allowed to cancel this order.",
        before_snapshot=before_snapshot,
    )
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
                _emit_allocation_event(
                    "allocation.released",
                    alloc["allocationId"],
                    {
                        "allocationId": alloc["allocationId"],
                        "orderId": order_id,
                        "orderLineId": alloc["orderLineId"],
                        "lotId": alloc["lotId"],
                        "releasedQty": alloc.get("allocatedQty", 0.0),
                        "reason": payload.reason if payload else None,
                    },
                    context,
                )
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
        with _MEMORY_ALLOCATION_LOCK:
            record = _get_order_record_or_404(order_id, action_name="order.cancel", context=context)
            allocations = _get_allocations_for_order(order_id)
            preorder_by_line_id = {
                line["orderLineId"]: line.get("sourcePreorderId") for line in record.get("lines", [])
            }
            lots_by_id = {alloc["lotId"]: _get_lot_record_or_404(alloc["lotId"]) for alloc in allocations}

            for alloc in allocations:
                lot = lots_by_id[alloc["lotId"]]
                lot["availableQty"] += alloc.get("allocatedQty", 0.0)
                lot["reservedQty"] = max(0.0, lot.get("reservedQty", 0.0) - alloc.get("allocatedQty", 0.0))
                store.save_lot(alloc["lotId"], lot)
                _record_inventory_movement(
                    lot_id=alloc["lotId"],
                    movement_type="release_reservation",
                    qty=float(alloc.get("allocatedQty", 0.0)),
                    order_id=order_id,
                    order_line_id=alloc["orderLineId"],
                    reason="allocation_cancelled",
                )
                source_preorder_id = preorder_by_line_id.get(alloc.get("orderLineId"))
                if source_preorder_id:
                    _decrement_preorder_allocated_qty(source_preorder_id, alloc.get("allocatedQty", 0.0))

            record["status"] = next_status
            postgres_sync.upsert_order(record)
            for alloc in allocations:
                alloc["status"] = AllocationStatus.cancelled.value
            postgres_sync.replace_allocations_for_order(order_id, allocations)
            store.save_allocations(order_id, allocations)
            for alloc in allocations:
                _emit_allocation_event(
                    "allocation.released",
                    alloc["allocationId"],
                    {
                        "allocationId": alloc["allocationId"],
                        "orderId": order_id,
                        "orderLineId": alloc["orderLineId"],
                        "lotId": alloc["lotId"],
                        "releasedQty": alloc.get("allocatedQty", 0.0),
                        "reason": payload.reason if payload else None,
                    },
                    context,
                )
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
