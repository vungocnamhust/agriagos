import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_preorder_code
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.core.gateway import assert_preorder_transition, check_idempotency, record_idempotency
from app.models.enums import PreorderStatus
from app.models.preorders import (
    AdjustPreorderRequest,
    CreatePreorderRequest,
    PreorderDetail,
    PreorderResponse,
)
from app.store import postgres_sync
from app.store import memory as store
from app.store._db import transaction as postgres_transaction


def _new_preorder_code() -> str:
    return generate_preorder_code()


def _build_preorder_detail(record: dict[str, Any]) -> PreorderDetail:
    return PreorderDetail(
        preorderId=record["preorderId"],
        preorderCode=record["preorderCode"],
        customerId=record["customerId"],
        productSkuId=record["productSkuId"],
        committedQty=record["committedQty"],
        allocatedQty=record["allocatedQty"],
        deliveredQty=record["deliveredQty"],
        remainingQty=record["remainingQty"],
        status=record["status"],
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
    append_audit_decision(
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
    return record


def create_preorder(payload: CreatePreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
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
        "remainingQty": payload.committedQty,
        "deliveryCadence": payload.deliveryCadence,
        "depositAmount": payload.depositAmount,
        "notes": payload.notes,
        "status": PreorderStatus.active.value,
        "startDate": payload.startDate,
    }
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


def get_preorder(preorder_id: str) -> PreorderDetail:
    record = _get_preorder_record_or_404(preorder_id)
    return _build_preorder_detail(record)


def adjust_preorder(preorder_id: str, payload: AdjustPreorderRequest) -> PreorderResponse:
    context = meta_context(payload.meta)
    record = _get_preorder_record_or_404(preorder_id, action_name="preorder.adjust", context=context)
    before_snapshot = copy.deepcopy(record)

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

    if payload.newCommittedQty < record["deliveredQty"]:
        _audit_preorder(
            "preorder.adjust",
            preorder_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="committed_qty_below_delivered",
            metadata={
                "message": (
                    f"newCommittedQty ({payload.newCommittedQty}) cannot be less than "
                    f"already delivered qty ({record['deliveredQty']})."
                )
            },
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"newCommittedQty ({payload.newCommittedQty}) cannot be less than "
                f"already delivered qty ({record['deliveredQty']})."
            ),
        )

    old_qty = record["committedQty"]
    record["committedQty"] = payload.newCommittedQty
    record["remainingQty"] = max(0.0, payload.newCommittedQty - record["deliveredQty"])
    result = PreorderResponse(data=_build_preorder_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        postgres_sync.upsert_preorder(record)
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
    return result
