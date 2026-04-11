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
    CustomerDuplicateCandidateSummary,
    CustomerDetail,
    CustomerPreferenceItem,
    CustomerResponse,
    CustomerSummary,
    PreferenceResponse,
    ReviewDuplicateCandidateRequest,
    UpdateCustomerRequest,
    UpsertPreferenceRequest,
)
from app.store import customers as customer_store
from app.store import memory as memory_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_ALLOWED_CANONICAL_PREFERENCE_SOURCES = {"human", "integration"}
_CANONICAL_PREFERENCE_ROLES = {"founder", "super_admin", "admin", "sales", "cskh"}
_DUPLICATE_REVIEW_ROLES = {"founder", "super_admin", "admin", "sales", "cskh"}
_CUSTOMER_WRITE_ROLES = {"founder", "super_admin", "admin", "sales", "cskh"}


def _normalize_actor_role(actor_role: str | None) -> str | None:
    if actor_role is None:
        return None
    normalized = actor_role.strip().lower().replace("/", " ").replace("-", " ")
    normalized = "_".join(normalized.split())
    alias_map = {
        "super_admin": "super_admin",
        "superadmin": "super_admin",
        "founder": "founder",
        "admin": "admin",
        "admin_van_hanh": "admin",
        "operations_admin": "admin",
        "sales": "sales",
        "cskh": "cskh",
        "customer_service": "cskh",
        "customer_success": "cskh",
        "integration": "integration",
        "ops": "ops",
    }
    return alias_map.get(normalized, normalized)


def _assert_can_confirm_canonical_preference(context: dict[str, Any], source: str, customer_id: str) -> None:
    actor_role = _normalize_actor_role(context.get("actor_role"))
    actor_id = context.get("actor_id")
    external_ref = context.get("external_ref")

    if actor_role == "integration":
        if source == "integration" and actor_id and external_ref:
            return
        _audit_customer(
            "customer.preference_upsert",
            customer_id,
            "denied",
            context,
            reason_code="untrusted_integration_source",
            metadata={
                "source": source,
                "message": "Integration confirmation requires source=integration, actorId, and externalRef.",
            },
        )
        raise HTTPException(
            status_code=403,
            detail="Integration confirmation requires source=integration, actorId, and externalRef.",
        )

    if source == "integration":
        _audit_customer(
            "customer.preference_upsert",
            customer_id,
            "denied",
            context,
            reason_code="source_actor_mismatch",
            metadata={"source": source, "actorRole": actor_role, "message": "Source integration requires actorRole=integration."},
        )
        raise HTTPException(status_code=403, detail="Source integration requires actorRole=integration.")

    if actor_role in _CANONICAL_PREFERENCE_ROLES:
        return

    _audit_customer(
        "customer.preference_upsert",
        customer_id,
        "denied",
        context,
        reason_code="forbidden_preference_confirmation",
        metadata={"source": source, "message": "Actor is not allowed to confirm canonical customer preferences."},
    )
    raise HTTPException(status_code=403, detail="Actor is not allowed to confirm canonical customer preferences.")


def _assert_can_review_duplicate_candidate(context: dict[str, Any], candidate_id: str) -> None:
    actor_role = _normalize_actor_role(context.get("actor_role"))
    if actor_role in _DUPLICATE_REVIEW_ROLES:
        return

    _audit_customer(
        "customer.duplicate_candidate_review",
        candidate_id,
        "denied",
        context,
        reason_code="forbidden_duplicate_candidate_review",
        metadata={"message": "Actor is not allowed to review customer duplicate candidates."},
    )
    raise HTTPException(status_code=403, detail="Actor is not allowed to review customer duplicate candidates.")


def _assert_can_write_customer(context: dict[str, Any], action_name: str, target_id: str, reason_code: str, detail: str) -> None:
    actor_role = _normalize_actor_role(context.get("actor_role"))
    if actor_role in _CUSTOMER_WRITE_ROLES:
        return

    _audit_customer(
        action_name,
        target_id,
        "denied",
        context,
        reason_code=reason_code,
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) > 9:
        return f"0{digits[2:]}"
    return digits


def _normalize_name(name: str) -> str:
    return " ".join(name.lower().split())


def _build_customer_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "customerId": record["customerId"],
        "customerCode": record["customerCode"],
        "fullName": record["fullName"],
        "phone": record["phone"],
        "status": record["status"],
        "createdAt": record.get("createdAt"),
        "tags": list(record.get("tags", [])),
    }


def _ordered_duplicate_pair(customer_id_a: str, customer_id_b: str) -> tuple[str, str]:
    primary_customer_id, suspected_customer_id = sorted((customer_id_a, customer_id_b))
    return primary_customer_id, suspected_customer_id


def _matching_duplicate_candidate(existing: dict[str, Any], candidate_customer: dict[str, Any]) -> tuple[str, float] | None:
    if existing["customerId"] == candidate_customer["customerId"]:
        return None
    if _normalize_name(existing.get("fullName", "")) != _normalize_name(candidate_customer.get("fullName", "")):
        return None

    existing_district = (existing.get("district") or "").strip().lower()
    candidate_district = (candidate_customer.get("district") or "").strip().lower()
    if existing_district and candidate_district and existing_district == candidate_district:
        return ("same_full_name_and_district", 0.95)

    existing_province = (existing.get("province") or "").strip().lower()
    candidate_province = (candidate_customer.get("province") or "").strip().lower()
    if existing_province and candidate_province and existing_province == candidate_province:
        return ("same_full_name_and_province", 0.8)

    return None


def _create_memory_duplicate_candidates(customer_record: dict[str, Any], context: dict[str, Any]) -> None:
    for existing in memory_store.list_customers():
        match = _matching_duplicate_candidate(existing, customer_record)
        if match is None:
            continue

        match_reason, match_score = match
        primary_customer_id, suspected_customer_id = _ordered_duplicate_pair(
            existing["customerId"],
            customer_record["customerId"],
        )
        if memory_store.has_open_duplicate_candidate(primary_customer_id, suspected_customer_id, match_reason):
            continue
        candidate_record = {
            "candidateId": str(uuid.uuid4()),
            "primaryCustomerId": primary_customer_id,
            "suspectedCustomerId": suspected_customer_id,
            "matchReason": match_reason,
            "matchScore": match_score,
            "status": "open",
            "detectedAt": memory_store.now_iso(),
            "reviewedAt": None,
            "reviewedBy": None,
            "note": None,
        }
        memory_store.save_duplicate_candidate(candidate_record["candidateId"], candidate_record)
        _audit_customer(
            "customer.duplicate_candidate_detect",
            existing["customerId"],
            "allowed",
            context,
            metadata={
                "candidateId": candidate_record["candidateId"],
                "suspectedCustomerId": customer_record["customerId"],
                "matchReason": match_reason,
                "matchScore": match_score,
            },
        )


def _create_duplicate_candidates(customer_record: dict[str, Any], context: dict[str, Any]) -> None:
    if postgres_enabled():
        for existing in customer_store.find_potential_duplicate_customers(customer_record):
            match = _matching_duplicate_candidate(existing, customer_record)
            if match is None:
                continue

            match_reason, match_score = match
            primary_customer_id, suspected_customer_id = _ordered_duplicate_pair(
                existing["customerId"],
                customer_record["customerId"],
            )
            candidate_record = {
                "candidateId": str(uuid.uuid4()),
                "primaryCustomerId": primary_customer_id,
                "suspectedCustomerId": suspected_customer_id,
                "matchReason": match_reason,
                "matchScore": match_score,
                "status": "open",
                "detectedAt": memory_store.now_iso(),
                "detectedBy": context.get("actor_id"),
                "reviewedAt": None,
                "reviewedBy": None,
                "note": None,
                "evidence": {
                    "fullName": customer_record.get("fullName"),
                    "province": customer_record.get("province"),
                    "district": customer_record.get("district"),
                },
            }
            customer_store.create_duplicate_candidate(candidate_record)
            _audit_customer(
                "customer.duplicate_candidate_detect",
                existing["customerId"],
                "allowed",
                context,
                metadata={
                    "candidateId": candidate_record["candidateId"],
                    "suspectedCustomerId": customer_record["customerId"],
                    "matchReason": match_reason,
                    "matchScore": match_score,
                },
            )
        return

    _create_memory_duplicate_candidates(customer_record, context)


def _fetch_preferences(customer_id: str) -> list[dict[str, Any]]:
    return (
        customer_store.fetch_customer_preferences(customer_id)
        if postgres_enabled()
        else memory_store.get_customer_preferences(customer_id)
    )


def _fetch_duplicate_candidates(customer_id: str) -> list[dict[str, Any]]:
    if postgres_enabled() and hasattr(customer_store, "list_customer_duplicate_candidates"):
        return customer_store.list_customer_duplicate_candidates(customer_id)
    return memory_store.list_customer_duplicate_candidates(customer_id)


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
    _assert_can_write_customer(
        context,
        "customer.create",
        "pending",
        "forbidden_customer_creation",
        "Actor is not allowed to create customers.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return CustomerResponse(**cached)

    phone_normalized = normalize_phone(payload.phone)

    if postgres_enabled():
        if customer_store.phone_exists(phone_normalized):
            _audit_customer(
                "customer.create",
                f"pending:{phone_normalized}",
                "denied",
                context,
                reason_code="duplicate_phone",
                metadata={"message": "Customer with this phone already exists."},
            )
            raise HTTPException(status_code=409, detail="Customer with this phone already exists.")
    else:
        if memory_store.customer_phone_exists(phone_normalized):
            _audit_customer(
                "customer.create",
                f"pending:{phone_normalized}",
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
        "phoneNormalized": phone_normalized,
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
        memory_store.save_customer(customer_id, record)
        _create_duplicate_candidates(record, context)
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
        normalized_phone = normalize_phone(phone)
        items = [c for c in items if normalize_phone(c["phone"]) == normalized_phone]
    if q:
        q_lower = q.lower()
        items = [
            c
            for c in items
            if q_lower in c["fullName"].lower()
            or q_lower in c["phone"]
            or q_lower in c["customerCode"].lower()
        ]
    if tag:
        items = [c for c in items if tag in c.get("tags", [])]
    return items


def get_customer(customer_id: str) -> CustomerDetail:
    record = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if record is None:
        record = memory_store.get_customer(customer_id)
    if not record:
        raise HTTPException(status_code=404, detail="Customer not found.")
    preferences = [CustomerPreferenceItem(**item) for item in _fetch_preferences(customer_id)]
    duplicate_candidates = [CustomerDuplicateCandidateSummary(**item) for item in _fetch_duplicate_candidates(customer_id)]
    return CustomerDetail(**record, preferences=preferences, duplicateCandidates=duplicate_candidates)


def update_customer(customer_id: str, payload: UpdateCustomerRequest) -> CustomerDetail:
    context = meta_context(payload.meta)
    _assert_can_write_customer(
        context,
        "customer.update",
        customer_id,
        "forbidden_customer_update",
        "Actor is not allowed to update customers.",
    )
    customer = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if customer is None:
        customer = memory_store.get_customer(customer_id)
    if customer is None:
        _audit_customer(
            "customer.update",
            customer_id,
            "denied",
            context,
            reason_code="customer_not_found",
            metadata={"message": "Customer not found."},
        )
        raise HTTPException(status_code=404, detail="Customer not found.")

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return CustomerDetail(**cached)

    before_snapshot = copy.deepcopy(customer)
    updated_customer = copy.deepcopy(customer)
    changed_fields: list[str] = []
    for payload_field, record_field in (
        ("fullName", "fullName"),
        ("channelSource", "channelSource"),
        ("defaultAddress", "defaultAddress"),
        ("district", "district"),
        ("province", "province"),
        ("notes", "notes"),
    ):
        value = getattr(payload, payload_field)
        if value is not None and updated_customer.get(record_field) != value:
            updated_customer[record_field] = value
            changed_fields.append(record_field)

    if payload.tags is not None and updated_customer.get("tags") != list(payload.tags):
        updated_customer["tags"] = list(payload.tags)
        changed_fields.append("tags")

    should_refresh_duplicate_candidates = any(
        field in {"fullName", "district", "province"}
        for field in changed_fields
    )

    with postgres_transaction() if postgres_enabled() else nullcontext():
        if postgres_enabled():
            customer_store.upsert_customer(updated_customer)
        memory_store.save_customer(customer_id, updated_customer)
        if should_refresh_duplicate_candidates:
            _create_duplicate_candidates(updated_customer, context)

        event = _emit_customer_event(
            event_name="customer.updated",
            customer_id=customer_id,
            payload={
                "customerId": customer_id,
                "changedFields": changed_fields,
                "beforeSummary": _build_customer_summary(before_snapshot),
                "afterSummary": _build_customer_summary(updated_customer),
            },
            context=context,
        )
        detailed_customer = get_customer(customer_id)
        _audit_customer(
            "customer.update",
            customer_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=updated_customer,
            event=event,
            metadata={"changedFields": changed_fields},
        )
        record_idempotency(
            key,
            detailed_customer.model_dump(mode="json"),
            operation_name="customer.update",
            request_hash=build_request_hash(payload, extra={"action": "customer.update", "customerId": customer_id}),
        )

    return detailed_customer


def list_customer_duplicate_candidates(customer_id: str) -> list[CustomerDuplicateCandidateSummary]:
    customer = customer_store.fetch_customer(customer_id) if postgres_enabled() else None
    if customer is None:
        customer = memory_store.get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found.")
    return [CustomerDuplicateCandidateSummary(**item) for item in _fetch_duplicate_candidates(customer_id)]


def list_duplicate_candidates() -> list[CustomerDuplicateCandidateSummary]:
    if postgres_enabled() and hasattr(customer_store, "list_duplicate_candidates"):
        return [CustomerDuplicateCandidateSummary(**item) for item in customer_store.list_duplicate_candidates()]
    return [CustomerDuplicateCandidateSummary(**item) for item in memory_store.list_duplicate_candidates()]


def review_duplicate_candidate(candidate_id: str, payload: ReviewDuplicateCandidateRequest) -> CustomerDuplicateCandidateSummary:
    context = meta_context(payload.meta)
    _assert_can_review_duplicate_candidate(context, candidate_id)
    candidate = customer_store.fetch_duplicate_candidate(candidate_id) if postgres_enabled() else None
    if candidate is None:
        candidate = memory_store.get_duplicate_candidate(candidate_id)
    if candidate is None:
        _audit_customer(
            "customer.duplicate_candidate_review",
            candidate_id,
            "denied",
            context,
            reason_code="duplicate_candidate_not_found",
            metadata={"message": "Duplicate candidate not found."},
        )
        raise HTTPException(status_code=404, detail="Duplicate candidate not found.")

    reviewed_at = memory_store.now_iso()
    reviewed_candidate = {
        **candidate,
        "status": payload.status,
        "note": payload.note,
        "reviewedAt": reviewed_at,
        "reviewedBy": context.get("actor_id"),
    }
    if postgres_enabled():
        stored_candidate = customer_store.review_duplicate_candidate(
            candidate_id,
            status=payload.status,
            note=payload.note,
            reviewed_by=context.get("actor_id"),
            reviewed_at=reviewed_at,
        )
        if stored_candidate is not None:
            reviewed_candidate = stored_candidate
    memory_store.save_duplicate_candidate(candidate_id, reviewed_candidate)
    _audit_customer(
        "customer.duplicate_candidate_review",
        reviewed_candidate["primaryCustomerId"],
        "allowed",
        context,
        before_snapshot=candidate,
        after_snapshot=reviewed_candidate,
        metadata={"candidateId": candidate_id, "status": payload.status},
    )
    return CustomerDuplicateCandidateSummary(**reviewed_candidate)


def upsert_preference(customer_id: str, payload: UpsertPreferenceRequest) -> PreferenceResponse:
    if payload.source not in _ALLOWED_CANONICAL_PREFERENCE_SOURCES:
        context = meta_context(payload.meta)
        _audit_customer(
            "customer.preference_upsert",
            customer_id,
            "denied",
            context,
            reason_code="invalid_preference_source",
            metadata={"source": payload.source, "message": "Source is not allowed for canonical preference writes."},
        )
        raise HTTPException(status_code=422, detail="Source is not allowed for canonical preference writes.")

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

    _assert_can_confirm_canonical_preference(context, payload.source, customer_id)

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return PreferenceResponse(**cached)

    before_snapshot = copy.deepcopy(existing_preferences := (
        _fetch_preferences(customer_id)
    ))

    confirmed_at = memory_store.now_iso()

    preference_record = {
        "tenantId": customer.get("tenantId", "default"),
        "preferenceType": payload.preferenceType,
        "preferenceValue": payload.preferenceValue,
        "source": payload.source,
        "confidenceLevel": payload.confidenceLevel,
        "confirmedBy": context.get("actor_id"),
        "confirmedAt": confirmed_at,
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
        source=payload.source,
        confidenceLevel=payload.confidenceLevel,
        confirmedBy=context.get("actor_id"),
        confirmedAt=confirmed_at,
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
                "confirmedBy": context.get("actor_id"),
                "confirmedAt": confirmed_at,
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
