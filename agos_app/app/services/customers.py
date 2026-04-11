import uuid
import re
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_customer_code
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
from app.store._db import is_enabled as postgres_enabled


def _new_customer_code() -> str:
    customer_code = generate_customer_code()
    if not postgres_enabled():
        return customer_code

    while customer_store.customer_code_exists(customer_code):
        customer_code = generate_customer_code()
    return customer_code


def create_customer(payload: CreateCustomerRequest) -> CustomerResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return CustomerResponse(**cached)

    if postgres_enabled():
        if customer_store.phone_exists(payload.phone):
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")
    else:
        if memory_store.customer_phone_exists(payload.phone):
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")

    customer_id = str(uuid.uuid4())
    customer_code = _new_customer_code()
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

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
    customer_store.upsert_customer(record)
    memory_store.save_customer(customer_id, record)

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
        status=record["status"],
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
    customer = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if customer is None:
        customer = memory_store.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return PreferenceResponse(**cached)

    preference_record = {
        "tenantId": customer.get("tenantId", "default"),
        "preferenceType": payload.preferenceType,
        "preferenceValue": payload.preferenceValue,
        "source": payload.source,
        "confidenceLevel": payload.confidenceLevel,
    }

    existing_preferences = (
        customer_store.fetch_customer_preferences(customer_id)
        if postgres_enabled()
        else memory_store.get_customer_preferences(customer_id)
    )

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

    if postgres_enabled():
        customer_store.upsert_customer_preference(customer_id, preference_record)
    memory_store.save_customer_preferences(customer_id, prefs)

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
