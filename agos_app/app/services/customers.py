import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.gateway import check_idempotency, record_idempotency
from app.models.customers import (
    CreateCustomerRequest,
    CustomerDetail,
    CustomerResponse,
    CustomerSummary,
    PreferenceResponse,
    UpsertPreferenceRequest,
)
from app.store import memory as store


def _new_customer_code() -> str:
    return f"CUST-{str(uuid.uuid4())[:8].upper()}"


def create_customer(payload: CreateCustomerRequest) -> CustomerResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return CustomerResponse(**cached)

    # Uniqueness check on phone
    for c in store._customers.values():
        if c["phone"] == payload.phone:
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")

    customer_id = str(uuid.uuid4())
    customer_code = _new_customer_code()
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

    record: dict[str, Any] = {
        "customerId": customer_id,
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
    store._customers[customer_id] = record

    events.emit(
        event_name="customer.created",
        aggregate_type="Customer",
        aggregate_id=customer_id,
        payload=record,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    summary = CustomerSummary(
        customerId=customer_id,
        customerCode=customer_code,
        fullName=payload.fullName,
        phone=payload.phone,
        tags=list(payload.tags),
    )
    result = CustomerResponse(data=summary)
    record_idempotency(key, result.model_dump())
    return result


def list_customers(
    phone: str | None,
    q: str | None,
    tag: str | None,
) -> list[dict[str, Any]]:
    items = list(store._customers.values())
    if phone:
        items = [c for c in items if c["phone"] == phone]
    if q:
        q_lower = q.lower()
        items = [c for c in items if q_lower in c["fullName"].lower() or q_lower in c["phone"]]
    if tag:
        items = [c for c in items if tag in c.get("tags", [])]
    return items


def get_customer(customer_id: str) -> CustomerDetail:
    record = store._customers.get(customer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return CustomerDetail(**record)


def upsert_preference(customer_id: str, payload: UpsertPreferenceRequest) -> PreferenceResponse:
    if customer_id not in store._customers:
        raise HTTPException(status_code=404, detail="Customer not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return PreferenceResponse(**cached)

    prefs = store._preferences[customer_id]
    # Replace existing preference of the same type if present
    updated = False
    for i, p in enumerate(prefs):
        if p["preferenceType"] == payload.preferenceType:
            prefs[i] = {
                "preferenceType": payload.preferenceType,
                "preferenceValue": payload.preferenceValue,
                "source": payload.source,
                "confidenceLevel": payload.confidenceLevel,
            }
            updated = True
            break
    if not updated:
        prefs.append({
            "preferenceType": payload.preferenceType,
            "preferenceValue": payload.preferenceValue,
            "source": payload.source,
            "confidenceLevel": payload.confidenceLevel,
        })

    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None
    events.emit(
        event_name="customer.preference_updated",
        aggregate_type="Customer",
        aggregate_id=customer_id,
        payload={
            "customerId": customer_id,
            "preferenceType": payload.preferenceType,
            "preferenceValue": payload.preferenceValue,
            "source": payload.source,
            "confidenceLevel": payload.confidenceLevel,
        },
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = PreferenceResponse(
        customerId=customer_id,
        preferenceType=payload.preferenceType,
        preferenceValue=payload.preferenceValue,
        confidenceLevel=payload.confidenceLevel,
    )
    record_idempotency(key, result.model_dump())
    return result
