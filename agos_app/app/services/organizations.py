from __future__ import annotations

import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_organization_code
from app.core.gateway import assert_organization_transition, check_idempotency, record_idempotency
from app.core.policy_sets import FOUNDATION_ADMIN_ROLES
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.organizations import (
    ActivateOrganizationRequest,
    CloseOrganizationRequest,
    CreateOrganizationRequest,
    OrganizationDetail,
    OrganizationResponse,
    OrganizationSummary,
    PauseOrganizationRequest,
    UpdateOrganizationRequest,
)
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import organizations as organization_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_ORGANIZATION_READ_ROLES = FOUNDATION_ADMIN_ROLES
_ORGANIZATION_WRITE_ROLES = FOUNDATION_ADMIN_ROLES


def _build_organization_detail(record: dict[str, Any]) -> OrganizationDetail:
    return OrganizationDetail(
        organizationId=record["organizationId"],
        organizationCode=record["organizationCode"],
        name=record["name"],
        organizationType=record["organizationType"],
        status=record["status"],
        region=record.get("region"),
        localitySummary=record.get("localitySummary"),
        representativeName=record.get("representativeName"),
        contactPhone=record.get("contactPhone"),
        contactEmail=record.get("contactEmail"),
        shortDescription=record.get("shortDescription"),
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _build_organization_summary(record: dict[str, Any]) -> OrganizationSummary:
    return OrganizationSummary(
        organizationId=record["organizationId"],
        organizationCode=record["organizationCode"],
        name=record["name"],
        organizationType=record["organizationType"],
        status=record["status"],
        region=record.get("region"),
        createdAt=record.get("createdAt"),
    )


def _emit_organization_event(
    event_name: str,
    organization_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Organization",
        aggregate_id=organization_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_organization(
    action_name: str,
    organization_id: str,
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
        target_type="Organization",
        target_id=organization_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_organization(
    context: dict[str, Any],
    *,
    action_name: str,
    organization_id: str,
    detail: str,
    before_snapshot: Any | None = None,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="Organization",
        target_id=organization_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _ORGANIZATION_WRITE_ROLES:
        return

    _audit_organization(
        action_name,
        organization_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code="forbidden_organization_write",
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_organization_record_or_404(
    organization_id: str,
    *,
    action_name: str = "organization.get",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = organization_store.fetch_organization(organization_id) if postgres_enabled() else memory_store.get_organization(organization_id)
    if record is not None:
        return record

    if context is not None:
        _audit_organization(
            action_name,
            organization_id,
            "denied",
            context,
            reason_code="organization_not_found",
            metadata={"message": "Organization not found."},
        )
    raise HTTPException(status_code=404, detail="Organization not found.")


def _new_organization_code() -> str:
    organization_code = generate_organization_code()
    if not postgres_enabled():
        return organization_code

    while organization_store.organization_code_exists(organization_code):
        organization_code = generate_organization_code()
    return organization_code


def create_organization(payload: CreateOrganizationRequest) -> OrganizationResponse:
    context = meta_context(payload.meta)
    _assert_can_write_organization(
        context,
        action_name="organization.create",
        organization_id="pending",
        detail="Actor is not allowed to create organizations.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrganizationResponse(**cached)

    timestamp = memory_store.now_iso()
    organization_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "organizationId": organization_id,
        "tenantId": "default",
        "organizationCode": _new_organization_code(),
        "name": payload.name,
        "organizationType": payload.organizationType.value,
        "status": "draft",
        "region": payload.region,
        "localitySummary": payload.localitySummary,
        "representativeName": payload.representativeName,
        "contactPhone": payload.contactPhone,
        "contactEmail": payload.contactEmail,
        "shortDescription": payload.shortDescription,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    result = OrganizationResponse(data=_build_organization_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        organization_store.upsert_organization(record)
        if not postgres_enabled():
            memory_store.save_organization(organization_id, record)
        event = _emit_organization_event("organization.created", organization_id, payload=record, context=context)
        _audit_organization("organization.create", organization_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="organization.create",
            request_hash=build_request_hash(payload, extra={"action": "organization.create"}),
        )

    return result


def list_organizations_for_actor(*, meta: Meta | None) -> list[OrganizationSummary]:
    authorize_read_surface(
        meta=meta,
        action_name="organization.list",
        target_type="Organization",
        target_id="collection",
        allowed_roles=_ORGANIZATION_READ_ROLES,
        reason_code="forbidden_organization_read",
        detail="Actor is not allowed to read organization details.",
    )
    items = organization_store.list_organizations() if postgres_enabled() else memory_store.list_organizations()
    return [_build_organization_summary(item) for item in items]


def get_organization_for_actor(organization_id: str, *, meta: Meta | None) -> OrganizationDetail:
    context = authorize_read_surface(
        meta=meta,
        action_name="organization.get",
        target_type="Organization",
        target_id=organization_id,
        allowed_roles=_ORGANIZATION_READ_ROLES,
        reason_code="forbidden_organization_read",
        detail="Actor is not allowed to read organization details.",
    )
    return _build_organization_detail(_get_organization_record_or_404(organization_id, context=context))


def update_organization(organization_id: str, payload: UpdateOrganizationRequest) -> OrganizationResponse:
    context = meta_context(payload.meta)
    record = _get_organization_record_or_404(organization_id, action_name="organization.update", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_organization(
        context,
        action_name="organization.update",
        organization_id=organization_id,
        detail="Actor is not allowed to update organizations.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrganizationResponse(**cached)

    changed_fields: list[str] = []
    for field_name in (
        "name",
        "region",
        "localitySummary",
        "representativeName",
        "contactPhone",
        "contactEmail",
        "shortDescription",
    ):
        new_value = getattr(payload, field_name)
        if new_value is None:
            continue
        record[field_name] = new_value
        changed_fields.append(field_name)

    if not changed_fields:
        _audit_organization(
            "organization.update",
            organization_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="empty_update_payload",
            metadata={"message": "Update payload must include at least one mutable field."},
        )
        raise HTTPException(status_code=422, detail="Update payload must include at least one mutable field.")

    record["updatedAt"] = memory_store.now_iso()
    result = OrganizationResponse(data=_build_organization_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        organization_store.upsert_organization(record)
        if not postgres_enabled():
            memory_store.save_organization(organization_id, record)
        event = _emit_organization_event(
            "organization.updated",
            organization_id,
            payload={
                "organizationId": organization_id,
                "changedFields": changed_fields,
                "afterSummary": _build_organization_summary(record).model_dump(),
            },
            context=context,
        )
        _audit_organization(
            "organization.update",
            organization_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="organization.update",
            request_hash=build_request_hash(payload, extra={"action": "organization.update", "organizationId": organization_id}),
        )
    return result


def activate_organization(organization_id: str, payload: ActivateOrganizationRequest) -> OrganizationResponse:
    context = meta_context(payload.meta)
    record = _get_organization_record_or_404(organization_id, action_name="organization.activate", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_organization(
        context,
        action_name="organization.activate",
        organization_id=organization_id,
        detail="Actor is not allowed to activate organizations.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrganizationResponse(**cached)

    try:
        next_status = assert_organization_transition(record, "activate")
    except HTTPException as exc:
        _audit_organization(
            "organization.activate",
            organization_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    old_status = record["status"]
    record["status"] = next_status
    record["updatedAt"] = memory_store.now_iso()
    result = OrganizationResponse(data=_build_organization_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        organization_store.upsert_organization(record)
        if not postgres_enabled():
            memory_store.save_organization(organization_id, record)
        event = _emit_organization_event(
            "organization.activated",
            organization_id,
            payload={"organizationId": organization_id, "oldStatus": old_status, "newStatus": next_status},
            context=context,
        )
        _audit_organization(
            "organization.activate",
            organization_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="organization.activate",
            request_hash=build_request_hash(payload, extra={"action": "organization.activate", "organizationId": organization_id}),
        )
    return result


def pause_organization(organization_id: str, payload: PauseOrganizationRequest) -> OrganizationResponse:
    context = meta_context(payload.meta)
    record = _get_organization_record_or_404(organization_id, action_name="organization.pause", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_organization(
        context,
        action_name="organization.pause",
        organization_id=organization_id,
        detail="Actor is not allowed to pause organizations.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrganizationResponse(**cached)

    try:
        next_status = assert_organization_transition(record, "pause")
    except HTTPException as exc:
        _audit_organization(
            "organization.pause",
            organization_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    old_status = record["status"]
    record["status"] = next_status
    record["updatedAt"] = memory_store.now_iso()
    result = OrganizationResponse(data=_build_organization_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        organization_store.upsert_organization(record)
        if not postgres_enabled():
            memory_store.save_organization(organization_id, record)
        event = _emit_organization_event(
            "organization.paused",
            organization_id,
            payload={
                "organizationId": organization_id,
                "oldStatus": old_status,
                "newStatus": next_status,
                "reason": payload.reason,
            },
            context=context,
        )
        _audit_organization(
            "organization.pause",
            organization_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"reason": payload.reason},
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="organization.pause",
            request_hash=build_request_hash(payload, extra={"action": "organization.pause", "organizationId": organization_id}),
        )
    return result


def close_organization(organization_id: str, payload: CloseOrganizationRequest) -> OrganizationResponse:
    context = meta_context(payload.meta)
    record = _get_organization_record_or_404(organization_id, action_name="organization.close", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_organization(
        context,
        action_name="organization.close",
        organization_id=organization_id,
        detail="Actor is not allowed to close organizations.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return OrganizationResponse(**cached)

    try:
        next_status = assert_organization_transition(record, "close")
    except HTTPException as exc:
        _audit_organization(
            "organization.close",
            organization_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    old_status = record["status"]
    record["status"] = next_status
    record["updatedAt"] = memory_store.now_iso()
    result = OrganizationResponse(data=_build_organization_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        organization_store.upsert_organization(record)
        if not postgres_enabled():
            memory_store.save_organization(organization_id, record)
        event = _emit_organization_event(
            "organization.closed",
            organization_id,
            payload={
                "organizationId": organization_id,
                "oldStatus": old_status,
                "newStatus": next_status,
                "reason": payload.reason,
            },
            context=context,
        )
        _audit_organization(
            "organization.close",
            organization_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"reason": payload.reason},
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="organization.close",
            request_hash=build_request_hash(payload, extra={"action": "organization.close", "organizationId": organization_id}),
        )
    return result