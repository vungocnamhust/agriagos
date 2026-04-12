from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.common import Meta
from app.services.read_authz import authorize_read_surface
from app.core.write_context import append_audit_decision
from app.store import audit as audit_store


COMMON_AUDIT_REASON_CODES = frozenset(
    {
        "state_transition_rejected",
        "customer_not_found",
        "preorder_not_found",
        "approval_required",
        "persistence_failed",
    }
)

ORDER_AUDIT_REASON_CODES = COMMON_AUDIT_REASON_CODES | frozenset(
    {
        "source_preorder_not_found",
        "source_preorder_not_linkable",
        "lot_not_found",
        "lot_not_released",
        "insufficient_lot_qty",
        "order_line_not_found",
        "order_line_qty_exceeded",
        "preorder_quota_exceeded",
        "allocation_atomic_rejected",
        "allocation_adjust_invalid_qty",
        "allocation_not_adjustable",
        "allocation_adjust_rejected",
        "allocation_not_releasable",
        "allocation_release_rejected",
        "packed_qty_invalid",
        "delivered_qty_invalid",
        "delivery_failure_reason_required",
        "order_not_found",
    }
)

PREORDER_AUDIT_REASON_CODES = COMMON_AUDIT_REASON_CODES | frozenset(
    {
        "invalid_committed_qty",
        "committed_qty_below_reserved_and_delivered",
        "preorder_has_allocations",
        "forbidden_preorder_read",
        "forbidden_preorder_write",
    }
)

LOT_AUDIT_REASON_CODES = COMMON_AUDIT_REASON_CODES | frozenset(
    {
        "lot_not_found",
        "invalid_quantity",
        "invalid_source_type",
        "invalid_source_ref",
        "source_ref_not_found",
        "invalid_unit",
        "adjusted_qty_below_released_qty",
        "invalid_released_quantity",
        "released_qty_exceeds_actual",
        "released_qty_below_reserved",
        "qc_release_guard_failed",
        "unsupported_evidence_type",
        "evidence_payload_missing",
        "unsupported_qc_result",
    }
)

ORDER_SENSITIVE_ACTIONS = frozenset(
    {
        "order.create",
        "order.confirm",
        "order.allocate",
        "allocation.adjust",
        "allocation.release",
        "order.pack",
        "order.ship",
        "order.deliver",
        "order.fail_delivery",
        "order.request_cancel",
        "order.cancel",
    }
)

PREORDER_SENSITIVE_ACTIONS = frozenset(
    {
        "preorder.create",
        "preorder.confirm",
        "preorder.activate",
        "preorder.adjust",
        "preorder.cancel",
    }
)

LOT_SENSITIVE_ACTIONS = frozenset(
    {
        "lot.create",
        "lot.processed_create",
        "lot.adjust_quantity",
        "lot.release",
        "lot.block",
        "lot.unblock",
        "lot.evidence_add",
        "lot.qc_review",
    }
)

ORDER_SNAPSHOT_KEYS = (
    "orderId",
    "orderCode",
    "customerId",
    "channel",
    "status",
    "paymentStatus",
    "deliveryDateExpected",
    "shippingAddress",
    "carrier",
    "trackingRef",
    "shippedAt",
    "deliveredAt",
    "proofRef",
    "failureReason",
    "cancelReason",
    "sourcePreorderFlag",
    "version",
)
ORDER_LINE_SNAPSHOT_KEYS = (
    "orderLineId",
    "productSkuId",
    "orderedQty",
    "allocatedQty",
    "packedQty",
    "deliveredQty",
    "unit",
    "status",
    "sourcePreorderId",
)
PREORDER_SNAPSHOT_KEYS = (
    "preorderId",
    "preorderCode",
    "customerId",
    "productSkuId",
    "committedQty",
    "allocatedQty",
    "deliveredQty",
    "remainingQty",
    "cancelledQty",
    "status",
    "startDate",
    "deliveryCadence",
    "version",
)
PREORDER_ADJUSTMENT_KEYS = (
    "oldCommittedQty",
    "newCommittedQty",
    "reason",
    "changedAt",
    "actorId",
)
LOT_SNAPSHOT_KEYS = (
    "lotId",
    "lotCode",
    "productSkuId",
    "sourceType",
    "sourceRefId",
    "harvestOrProductionDate",
    "actualQty",
    "availableQty",
    "reservedQty",
    "releasedQty",
    "unit",
    "status",
    "qualityStatus",
    "version",
)


def _project_mapping(snapshot: Any, keys: tuple[str, ...]) -> dict[str, Any] | Any:
    if not isinstance(snapshot, dict):
        return snapshot
    return {key: snapshot[key] for key in keys if key in snapshot}


def _project_order_snapshot(snapshot: Any) -> dict[str, Any] | Any:
    projected = _project_mapping(snapshot, ORDER_SNAPSHOT_KEYS)
    if not isinstance(projected, dict):
        return projected
    if isinstance(snapshot, dict) and isinstance(snapshot.get("lines"), list):
        projected["lines"] = [
            _project_mapping(line, ORDER_LINE_SNAPSHOT_KEYS)
            for line in snapshot.get("lines", [])
            if isinstance(line, dict)
        ]
    return projected


def _project_preorder_snapshot(snapshot: Any) -> dict[str, Any] | Any:
    projected = _project_mapping(snapshot, PREORDER_SNAPSHOT_KEYS)
    if not isinstance(projected, dict):
        return projected
    if isinstance(snapshot, dict) and isinstance(snapshot.get("adjustmentHistory"), list):
        projected["adjustmentHistory"] = [
            _project_mapping(entry, PREORDER_ADJUSTMENT_KEYS)
            for entry in snapshot.get("adjustmentHistory", [])
            if isinstance(entry, dict)
        ]
    return projected


def _project_lot_snapshot(snapshot: Any) -> dict[str, Any] | Any:
    return _project_mapping(snapshot, LOT_SNAPSHOT_KEYS)


def _reason_registry_for_target(target_type: str) -> frozenset[str] | None:
    if target_type == "Order":
        return ORDER_AUDIT_REASON_CODES
    if target_type == "Preorder":
        return PREORDER_AUDIT_REASON_CODES
    if target_type == "Lot":
        return LOT_AUDIT_REASON_CODES
    return None


def _apply_snapshot_policy(
    *,
    target_type: str,
    action_name: str,
    decision: str,
    before_snapshot: Any | None,
    after_snapshot: Any | None,
) -> tuple[Any | None, Any | None]:
    if target_type == "Order" and action_name in ORDER_SENSITIVE_ACTIONS:
        before_snapshot = _project_order_snapshot(before_snapshot)
        after_snapshot = _project_order_snapshot(after_snapshot)
    elif target_type == "Preorder" and action_name in PREORDER_SENSITIVE_ACTIONS:
        before_snapshot = _project_preorder_snapshot(before_snapshot)
        after_snapshot = _project_preorder_snapshot(after_snapshot)
    elif target_type == "Lot" and action_name in LOT_SENSITIVE_ACTIONS:
        before_snapshot = _project_lot_snapshot(before_snapshot)
        after_snapshot = _project_lot_snapshot(after_snapshot)

    if decision in {"denied", "failed", "escalated"}:
        after_snapshot = None

    return before_snapshot, after_snapshot


def standardize_audit_payload(
    *,
    target_type: str,
    action_name: str,
    decision: str,
    reason_code: str | None,
    before_snapshot: Any | None,
    after_snapshot: Any | None,
    metadata: dict[str, Any] | None,
) -> dict[str, Any]:
    registry = _reason_registry_for_target(target_type)
    if registry is not None and reason_code is not None and reason_code not in registry:
        raise ValueError(f"Unknown audit reason code for {target_type}: {reason_code}")

    standardized_before, standardized_after = _apply_snapshot_policy(
        target_type=target_type,
        action_name=action_name,
        decision=decision,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return {
        "reason_code": reason_code,
        "before_snapshot": standardized_before,
        "after_snapshot": standardized_after,
        "metadata": dict(metadata or {}),
    }


def append_domain_audit_decision(
    *,
    action_name: str,
    target_type: str,
    target_id: str,
    decision: str,
    context: dict[str, Any],
    before_snapshot: Any | None = None,
    after_snapshot: Any | None = None,
    reason_code: str | None = None,
    event: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    standardized = standardize_audit_payload(
        target_type=target_type,
        action_name=action_name,
        decision=decision,
        reason_code=reason_code,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        metadata=metadata,
    )
    return append_audit_decision(
        action_name=action_name,
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        context=context,
        before_snapshot=standardized["before_snapshot"],
        after_snapshot=standardized["after_snapshot"],
        reason_code=standardized["reason_code"],
        event=event,
        metadata=standardized["metadata"],
    )


def query_audit_logs(
    *,
    target_type: str | None = None,
    target_id: str | None = None,
    action_name: str | None = None,
    decision: str | None = None,
    reason_code: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    meta: Meta | None = None,
) -> list[dict[str, object]]:
    authorize_read_surface(
        meta=meta,
        action_name="audit.query",
        target_type="AuditLog",
        target_id="query",
        allowed_roles={"founder", "super_admin", "admin", "accountant"},
        reason_code="forbidden_audit_query",
        detail="Actor is not allowed to query the audit log.",
    )
    return audit_store.query_audit_logs(
        target_type=target_type,
        target_id=target_id,
        action_name=action_name,
        decision=decision,
        reason_code=reason_code,
        correlation_id=correlation_id,
        actor_id=actor_id,
        actor_role=actor_role,
        created_from=created_from.isoformat() if created_from is not None else None,
        created_to=created_to.isoformat() if created_to is not None else None,
    )