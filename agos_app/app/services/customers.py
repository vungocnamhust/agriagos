import copy
import uuid
import re
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_customer_code
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.core.gateway import check_idempotency, record_idempotency
from app.models.customers import (
    CreateCustomerRequest,
    CustomerDetail,
    CustomerResponse,
    CustomerSummary,
    PreferenceResponse,
    UpsertPreferenceRequest,
)
from app.store import customers as customer_store
from app.store import memory as memory_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


def _new_customer_code() -> str:
    customer_code = generate_customer_code()
    if not postgres_enabled():
        return customer_code

    while customer_store.customer_code_exists(customer_code):
        customer_code = generate_customer_code()
    return customer_code


def _emit_customer_event(
    event_name: str,
    customer_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Customer",
        aggregate_id=customer_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_customer(
    action_name: str,
    customer_id: str,
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
        target_type="Customer",
        target_id=customer_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def create_customer(payload: CreateCustomerRequest) -> CustomerResponse:
    context = meta_context(payload.meta)
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return CustomerResponse(**cached)

    if postgres_enabled():
        if customer_store.phone_exists(payload.phone):
            _audit_customer(
                "customer.create",
                f"pending:{payload.phone}",
                "denied",
                context,
                reason_code="duplicate_phone",
                metadata={"message": "Customer with this phone already exists."},
            )
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")
    else:
        if memory_store.customer_phone_exists(payload.phone):
            _audit_customer(
                "customer.create",
                f"pending:{payload.phone}",
                "denied",
                context,
                reason_code="duplicate_phone",
                metadata={"message": "Customer with this phone already exists."},
            )
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")

    customer_id = str(uuid.uuid4())
    customer_code = _new_customer_code()

    record: dict[str, Any] = {
        "customerId": customer_id,
        "tenantId": "default",
        "customerCode": customer_code,
        "fullName": payload.fullName,
        "phone": payload.phone,
        "channelSource": payload.channelSource,
        "defaultAddress": payload.defaultAddress,
        "district": payload.district,
        "province": payload.province,
        "tags": list(payload.tags),
        "notes": payload.notes,
        "status": "active",
    }

    summary = CustomerSummary(
        customerId=customer_id,
        customerCode=customer_code,
        fullName=payload.fullName,
        phone=payload.phone,
        status=record["status"],
        tags=list(payload.tags),
    )
    result = CustomerResponse(data=summary)
    with postgres_transaction() if postgres_enabled() else nullcontext():
        customer_store.upsert_customer(record)
        event = _emit_customer_event(
            event_name="customer.created",
            customer_id=customer_id,
            payload=record,
            context=context,
        )
        _audit_customer("customer.create", customer_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="customer.create",
            request_hash=build_request_hash(payload, extra={"action": "customer.create"}),
        )

    memory_store.save_customer(customer_id, record)
    return result


def list_customers(
    phone: str | None,
    q: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    if tag and not re.fullmatch(r"[A-Za-z0-9_-]+", tag):
        raise HTTPException(status_code=422, detail="Invalid tag format.")

    if postgres_enabled():
        return customer_store.list_customers(phone, q, tag)

    items = memory_store.list_customers()
    if phone:
        items = [c for c in items if c["phone"] == phone]
    if q:
        q_lower = q.lower()
        items = [c for c in items if q_lower in c["fullName"].lower() or q_lower in c["phone"]]
    if tag:
        items = [c for c in items if tag in c.get("tags", [])]
    return items


def get_customer(customer_id: str) -> CustomerDetail:
    record = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if record is None:
        record = memory_store.get_customer(customer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return CustomerDetail(**record)


def upsert_preference(customer_id: str, payload: UpsertPreferenceRequest) -> PreferenceResponse:
    context = meta_context(payload.meta)
    customer = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if customer is None:
        customer = memory_store.get_customer(customer_id)
    if customer is None:
        _audit_customer(
            "customer.preference_upsert",
            customer_id,
            "denied",
            context,
            reason_code="customer_not_found",
            metadata={"message": "Customer not found."},
        )
        raise HTTPException(status_code=404, detail="Customer not found.")

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreferenceResponse(**cached)

    before_snapshot = copy.deepcopy(existing_preferences := (
        customer_store.fetch_customer_preferences(customer_id)
        if postgres_enabled()
        else memory_store.get_customer_preferences(customer_id)
    ))

    preference_record = {
        "tenantId": customer.get("tenantId", "default"),
        "preferenceType": payload.preferenceType,
        "preferenceValue": payload.preferenceValue,
        "source": payload.source,
        "confidenceLevel": payload.confidenceLevel,
    }

    prefs = list(existing_preferences)
    # Replace existing preference of the same type if present
    updated = False
    for index, preference in enumerate(prefs):
        if preference["preferenceType"] == payload.preferenceType:
            prefs[index] = preference_record
            updated = True
            break
    if not updated:
        prefs.append(preference_record)

    result = PreferenceResponse(
        customerId=customer_id,
        preferenceType=payload.preferenceType,
        preferenceValue=payload.preferenceValue,
        confidenceLevel=payload.confidenceLevel,
    )
    with postgres_transaction() if postgres_enabled() else nullcontext():
        if postgres_enabled():
            customer_store.upsert_customer_preference(customer_id, preference_record)
        event = _emit_customer_event(
            event_name="customer.preference_updated",
            customer_id=customer_id,
            payload={
                "customerId": customer_id,
                "preferenceType": payload.preferenceType,
                "preferenceValue": payload.preferenceValue,
                "source": payload.source,
                "confidenceLevel": payload.confidenceLevel,
            },
            context=context,
        )
        _audit_customer(
            "customer.preference_upsert",
            customer_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=prefs,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="customer.preference_upsert",
            request_hash=build_request_hash(payload, extra={"action": "customer.preference_upsert", "customerId": customer_id}),
        )

    memory_store.save_customer_preferences(customer_id, prefs)
    return result
