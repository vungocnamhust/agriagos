import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_preorder_code
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


def _get_preorder_record_or_404(preorder_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_preorder(preorder_id)
        if record:
            store._preorders[preorder_id] = record
    else:
        record = store._preorders.get(preorder_id)

    if not record:
        raise HTTPException(status_code=404, detail="Preorder not found.")
    return record


def create_preorder(payload: CreatePreorderRequest) -> PreorderResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    customer_exists = payload.customerId in store._customers
    if postgres_sync.is_enabled():
        customer_exists = postgres_sync.customer_exists(payload.customerId)

    if not customer_exists:
        raise HTTPException(status_code=404, detail="Customer not found.")

    preorder_id = str(uuid.uuid4())
    preorder_code = _new_preorder_code()
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

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
    postgres_sync.upsert_preorder(record)
    if not postgres_sync.is_enabled():
        store._preorders[preorder_id] = record

    events.emit(
        "preorder.placed",
        "Preorder",
        preorder_id,
        payload=record,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = PreorderResponse(data=_build_preorder_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def get_preorder(preorder_id: str) -> PreorderDetail:
    record = _get_preorder_record_or_404(preorder_id)
    return _build_preorder_detail(record)


def adjust_preorder(preorder_id: str, payload: AdjustPreorderRequest) -> PreorderResponse:
    record = _get_preorder_record_or_404(preorder_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return PreorderResponse(**cached)

    assert_preorder_transition(record, "adjust")

    if payload.newCommittedQty < record["deliveredQty"]:
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
    postgres_sync.upsert_preorder(record)

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    events.emit(
        "preorder.adjusted",
        "Preorder",
        preorder_id,
        payload={
            "preorderId": preorder_id,
            "oldCommittedQty": old_qty,
            "newCommittedQty": payload.newCommittedQty,
            "reason": payload.reason,
        },
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = PreorderResponse(data=_build_preorder_detail(record))
    record_idempotency(key, result.model_dump())
    return result
