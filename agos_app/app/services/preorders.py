import copy
import uuid
from contextlib import nullcontext
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_preorder_code
from app.core.write_context import build_request_hash, meta_context
from app.core.gateway import assert_preorder_transition, check_idempotency, record_idempotency
from app.models.common import Meta
from app.models.enums import PreorderStatus
from app.models.preorders import (
    ActivatePreorderRequest,
    AdjustPreorderRequest,
    CancelPreorderRequest,
    ConfirmPreorderRequest,
    CreatePreorderRequest,
    PreorderAdjustmentEntry,
    PreorderDetail,
    PreorderResponse,
)
from app.services import audit as audit_service
from app.store import postgres_sync
from app.store import memory as store
from app.store._db import transaction as postgres_transaction


_PREORDER_READ_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh", "ops", "accountant"})
_PREORDER_WRITE_ROLES = frozenset({"founder", "super_admin", "admin", "sales", "cskh"})


def _new_preorder_code() -> str:
    return generate_preorder_code()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _recompute_remaining_qty(record: dict[str, Any]) -> float:
    committed_qty = Decimal(str(record.get("committedQty", 0.0) or 0.0))
    allocated_qty = Decimal(str(record.get("allocatedQty", 0.0) or 0.0))
    delivered_qty = Decimal(str(record.get("deliveredQty", 0.0) or 0.0))
    cancelled_qty = Decimal(str(record.get("cancelledQty", 0.0) or 0.0))
    return float(max(Decimal("0"), committed_qty - allocated_qty - delivered_qty - cancelled_qty))


def _normalized_preorder_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    normalized.setdefault("allocatedQty", 0.0)
    normalized.setdefault("deliveredQty", 0.0)
    normalized.setdefault("cancelledQty", 0.0)
    normalized.setdefault("adjustmentHistory", [])
    normalized["remainingQty"] = _recompute_remaining_qty(normalized)
    return normalized


def _build_adjustment_history(record: dict[str, Any]) -> list[PreorderAdjustmentEntry]:
    return [PreorderAdjustmentEntry(**entry) for entry in record.get("adjustmentHistory", [])]


def _build_preorder_detail(record: dict[str, Any]) -> PreorderDetail:
    normalized = _normalized_preorder_record(record)
    return PreorderDetail(
        preorderId=normalized["preorderId"],
        preorderCode=normalized["preorderCode"],
        customerId=normalized["customerId"],
        productSkuId=normalized["productSkuId"],
        committedQty=normalized["committedQty"],
        allocatedQty=normalized["allocatedQty"],
        deliveredQty=normalized["deliveredQty"],
        remainingQty=normalized["remainingQty"],
        cancelledQty=normalized.get("cancelledQty", 0.0),
        status=normalized["status"],
        startDate=normalized.get("startDate"),
        adjustmentHistory=_build_adjustment_history(normalized),
    )


def _emit_preorder_event(
    event_name: str,
    preorder_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Preorder",
        aggregate_id=preorder_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_preorder(
    action_name: str,
    preorder_id: str,
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
        target_type="Preorder",
        target_id=preorder_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _effective_preorder_actor_role(context: dict[str, Any], *, allow_delegated_agent: bool = False) -> str | None:
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role != "agent" or not allow_delegated_agent:
        return actor_role

    delegated_actor_role = normalize_actor_role(context.get("delegated_actor_role"))
    return delegated_actor_role or actor_role


def _assert_preorder_access(
    *,
    context: dict[str, Any],
    action_name: str,
    preorder_id: str,
    allowed_roles: frozenset[str],
    reason_code: str,
    detail: str,
    before_snapshot: Any | None = None,
    allow_delegated_agent: bool = False,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="Preorder",
        target_id=preorder_id,
        context=context,
    )

    actor_role = _effective_preorder_actor_role(context, allow_delegated_agent=allow_delegated_agent)
    if actor_role in allowed_roles:
        return

    _audit_preorder(
        action_name,
        preorder_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, "effectiveActorRole": actor_role},
    )
    raise HTTPException(status_code=403, detail=detail)


def _raise_preorder_denied(
    *,
    action_name: str,
    preorder_id: str,
    context: dict[str, Any],
    detail: str,
    reason_code: str,
    status_code: int = 422,
    before_snapshot: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _audit_preorder(
        action_name,
        preorder_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _get_preorder_record_or_404(
    preorder_id: str,
    *,
    action_name: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_preorder(preorder_id)
        if record:
            store.save_preorder(preorder_id, record)
    else:
        record = store.get_preorder(preorder_id)

    if not record:
        if action_name and context is not None:
            _audit_preorder(
                action_name,
                preorder_id,
                "denied",
                context,
                reason_code="preorder_not_found",
                metadata={"message": "Preorder not found."},
            )
        raise HTTPException(status_code=404, detail="Preorder not found.")
    return _normalized_preorder_record(record)


def create_preorder(payload: CreatePreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    _assert_preorder_access(
        context=context,
        action_name="preorder.create",
        preorder_id=f"pending:{payload.customerId}",
        allowed_roles=_PREORDER_WRITE_ROLES,
        reason_code="forbidden_preorder_write",
        detail="Actor is not allowed to create preorders.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    customer_exists = store.has_customer(payload.customerId)
    if postgres_sync.is_enabled():
        customer_exists = postgres_sync.customer_exists(payload.customerId)

    if not customer_exists:
        _audit_preorder(
            "preorder.create",
            f"pending:{payload.customerId}",
            "denied",
            context,
            reason_code="customer_not_found",
            metadata={"message": "Customer not found."},
        )
        raise HTTPException(status_code=404, detail="Customer not found.")

    preorder_id = str(uuid.uuid4())
    preorder_code = _new_preorder_code()

    record: dict[str, Any] = {
        "preorderId": preorder_id,
        "tenantId": "default",
        "preorderCode": preorder_code,
        "customerId": payload.customerId,
        "productSkuId": payload.productSkuId,
        "committedQty": payload.committedQty,
        "allocatedQty": 0.0,
        "deliveredQty": 0.0,
        "cancelledQty": 0.0,
        "remainingQty": payload.committedQty,
        "deliveryCadence": payload.deliveryCadence,
        "depositAmount": payload.depositAmount,
        "notes": payload.notes,
        "status": PreorderStatus.draft.value,
        "startDate": payload.startDate,
        "adjustmentHistory": [],
    }
    record["remainingQty"] = _recompute_remaining_qty(record)
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
        event = _emit_preorder_event(
            "preorder.placed",
            preorder_id,
            payload=record,
            context=context,
        )
        _audit_preorder("preorder.create", preorder_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="preorder.create",
            request_hash=build_request_hash(payload, extra={"action": "preorder.create"}),
        )

    if not postgres_sync.is_enabled():
        store.save_preorder(preorder_id, record)
    return result


def get_preorder(preorder_id: str, meta: Meta | None = None) -> PreorderDetail:
    context = meta_context(meta)
    _assert_preorder_access(
        context=context,
        action_name="preorder.get",
        preorder_id=preorder_id,
        allowed_roles=_PREORDER_READ_ROLES,
        reason_code="forbidden_preorder_read",
        detail="Actor is not allowed to read preorder details.",
        allow_delegated_agent=True,
    )
    record = _get_preorder_record_or_404(preorder_id)
    return _build_preorder_detail(record)


def confirm_preorder(preorder_id: str, payload: ConfirmPreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    record = _get_preorder_record_or_404(preorder_id, action_name="preorder.confirm", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_preorder_access(
        context=context,
        action_name="preorder.confirm",
        preorder_id=preorder_id,
        allowed_roles=_PREORDER_WRITE_ROLES,
        reason_code="forbidden_preorder_write",
        detail="Actor is not allowed to confirm preorders.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    try:
        next_status = assert_preorder_transition(record, "confirm")
    except HTTPException as exc:
        _audit_preorder(
            "preorder.confirm",
            preorder_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    record["status"] = next_status
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
        event = _emit_preorder_event(
            "preorder.confirmed",
            preorder_id,
            payload={"preorderId": preorder_id, "status": next_status},
            context=context,
        )
        _audit_preorder(
            "preorder.confirm",
            preorder_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="preorder.confirm",
            request_hash=build_request_hash(payload, extra={"action": "preorder.confirm", "preorderId": preorder_id}),
        )
    if not postgres_sync.is_enabled():
        store.save_preorder(preorder_id, record)
    return result


def activate_preorder(preorder_id: str, payload: ActivatePreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    record = _get_preorder_record_or_404(preorder_id, action_name="preorder.activate", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_preorder_access(
        context=context,
        action_name="preorder.activate",
        preorder_id=preorder_id,
        allowed_roles=_PREORDER_WRITE_ROLES,
        reason_code="forbidden_preorder_write",
        detail="Actor is not allowed to activate preorders.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    try:
        next_status = assert_preorder_transition(record, "activate")
    except HTTPException as exc:
        _audit_preorder(
            "preorder.activate",
            preorder_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    record["status"] = next_status
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
        event = _emit_preorder_event(
            "preorder.activated",
            preorder_id,
            payload={"preorderId": preorder_id, "status": next_status, "activeFrom": record.get("startDate")},
            context=context,
        )
        _audit_preorder(
            "preorder.activate",
            preorder_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="preorder.activate",
            request_hash=build_request_hash(payload, extra={"action": "preorder.activate", "preorderId": preorder_id}),
        )
    if not postgres_sync.is_enabled():
        store.save_preorder(preorder_id, record)
    return result


def adjust_preorder(preorder_id: str, payload: AdjustPreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    record = _get_preorder_record_or_404(preorder_id, action_name="preorder.adjust", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_preorder_access(
        context=context,
        action_name="preorder.adjust",
        preorder_id=preorder_id,
        allowed_roles=_PREORDER_WRITE_ROLES,
        reason_code="forbidden_preorder_write",
        detail="Actor is not allowed to adjust preorders.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    try:
        assert_preorder_transition(record, "adjust")
    except HTTPException as exc:
        _audit_preorder(
            "preorder.adjust",
            preorder_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    if payload.newCommittedQty <= 0:
        _raise_preorder_denied(
            action_name="preorder.adjust",
            preorder_id=preorder_id,
            context=context,
            detail="newCommittedQty must be positive.",
            reason_code="invalid_committed_qty",
            before_snapshot=before_snapshot,
        )

    minimum_committed_qty = float(
        Decimal(str(record["allocatedQty"]))
        + Decimal(str(record["deliveredQty"]))
        + Decimal(str(record.get("cancelledQty", 0.0)))
    )
    if payload.newCommittedQty < minimum_committed_qty:
        _raise_preorder_denied(
            action_name="preorder.adjust",
            preorder_id=preorder_id,
            context=context,
            detail=(
                f"newCommittedQty ({payload.newCommittedQty}) cannot be less than "
                f"allocated + delivered qty ({minimum_committed_qty})."
            ),
            reason_code="committed_qty_below_reserved_and_delivered",
            before_snapshot=before_snapshot,
        )

    old_qty = record["committedQty"]
    record["committedQty"] = payload.newCommittedQty
    record.setdefault("adjustmentHistory", [])
    record["adjustmentHistory"] = [
        adjustment_entry := {
            "oldCommittedQty": old_qty,
            "newCommittedQty": payload.newCommittedQty,
            "reason": payload.reason,
            "changedAt": _now_iso(),
            "actorId": context.get("actor_id"),
        },
        *record["adjustmentHistory"],
    ]
    record["remainingQty"] = _recompute_remaining_qty(record)
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
        if postgres_sync.is_enabled():
            postgres_sync.append_preorder_adjustment(preorder_id, adjustment_entry)
        event = _emit_preorder_event(
            "preorder.adjusted",
            preorder_id,
            payload={
                "preorderId": preorder_id,
                "oldCommittedQty": old_qty,
                "newCommittedQty": payload.newCommittedQty,
                "reason": payload.reason,
            },
            context=context,
        )
        _audit_preorder(
            "preorder.adjust",
            preorder_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="preorder.adjust",
            request_hash=build_request_hash(payload, extra={"action": "preorder.adjust", "preorderId": preorder_id}),
        )
    if not postgres_sync.is_enabled():
        store.save_preorder(preorder_id, record)
    return result


def cancel_preorder(preorder_id: str, payload: CancelPreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    record = _get_preorder_record_or_404(preorder_id, action_name="preorder.cancel", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_preorder_access(
        context=context,
        action_name="preorder.cancel",
        preorder_id=preorder_id,
        allowed_roles=_PREORDER_WRITE_ROLES,
        reason_code="forbidden_preorder_write",
        detail="Actor is not allowed to cancel preorders.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    try:
        next_status = assert_preorder_transition(record, "cancel")
    except HTTPException as exc:
        _audit_preorder(
            "preorder.cancel",
            preorder_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    allocated_qty = float(record.get("allocatedQty", 0.0) or 0.0)
    if allocated_qty > 0:
        _raise_preorder_denied(
            action_name="preorder.cancel",
            preorder_id=preorder_id,
            context=context,
            detail="Preorder cannot be cancelled while allocated qty exists.",
            reason_code="preorder_has_allocations",
            before_snapshot=before_snapshot,
        )

    record["status"] = next_status
    record["cancelledQty"] = max(
        0.0,
        float(
            Decimal(str(record.get("committedQty", 0.0)))
            - Decimal(str(record.get("allocatedQty", 0.0)))
            - Decimal(str(record.get("deliveredQty", 0.0)))
        ),
    )
    record["remainingQty"] = _recompute_remaining_qty(record)
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
        event = _emit_preorder_event(
            "preorder.cancelled",
            preorder_id,
            payload={
                "preorderId": preorder_id,
                "cancelledQty": record["cancelledQty"],
                "reason": payload.reason,
            },
            context=context,
        )
        _audit_preorder(
            "preorder.cancel",
            preorder_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="preorder.cancel",
            request_hash=build_request_hash(payload, extra={"action": "preorder.cancel", "preorderId": preorder_id}),
        )
    if not postgres_sync.is_enabled():
        store.save_preorder(preorder_id, record)
    return result
