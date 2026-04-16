from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_actor_code
from app.core.policy_sets import FOUNDATION_ADMIN_ROLES
from app.core.gateway import check_idempotency, record_idempotency
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.actor_authority import (
    ActorAffiliationDetail,
    ActorAffiliationResponse,
    ActorIdentityDetail,
    ActorIdentityResponse,
    CreateActorAffiliationRequest,
    CreateActorIdentityRequest,
)
from app.models.common import Meta
from app.services.read_authz import authorize_read_surface
from app.store import actor_authority as actor_authority_store
from app.store import memory as memory_store
from app.store import organizations as organization_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_ACTOR_IDENTITY_READ_ROLES = FOUNDATION_ADMIN_ROLES
_ACTOR_IDENTITY_WRITE_ROLES = FOUNDATION_ADMIN_ROLES


def _build_actor_identity_detail(record: dict[str, Any]) -> ActorIdentityDetail:
    return ActorIdentityDetail(
        actorId=record["actorId"],
        actorCode=record["actorCode"],
        actorType=record["actorType"],
        displayName=record["displayName"],
        status=record["status"],
        primaryPhone=record.get("primaryPhone"),
        primaryEmail=record.get("primaryEmail"),
        externalMappingsJson=record.get("externalMappingsJson") or {},
        metadata=record.get("metadata") or {},
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _build_actor_affiliation_detail(record: dict[str, Any]) -> ActorAffiliationDetail:
    return ActorAffiliationDetail(
        actorAffiliationId=record["actorAffiliationId"],
        actorId=record["actorId"],
        organizationId=record.get("organizationId"),
        projectScopeId=record.get("projectScopeId"),
        affiliationKind=record["affiliationKind"],
        status=record["status"],
        effectiveAt=record["effectiveAt"],
        endedAt=record.get("endedAt"),
        confirmedBy=record.get("confirmedBy"),
        confirmedAt=record.get("confirmedAt"),
        metadata=record.get("metadata") or {},
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _emit_actor_authority_event(
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_actor_authority(
    action_name: str,
    target_type: str,
    target_id: str,
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
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_actor_authority(
    context: dict[str, Any],
    *,
    action_name: str,
    target_type: str,
    target_id: str,
    detail: str,
    reason_code: str,
    before_snapshot: Any | None = None,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type=target_type,
        target_id=target_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _ACTOR_IDENTITY_WRITE_ROLES:
        return

    _audit_actor_authority(
        action_name,
        target_type,
        target_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_actor_identity_record_or_404(
    actor_id: str,
    *,
    action_name: str = "actor_identity.get",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = actor_authority_store.fetch_actor_identity(actor_id) if postgres_enabled() else memory_store.get_actor_identity(actor_id)
    if record is not None:
        return record

    if context is not None:
        _audit_actor_authority(
            action_name,
            "ActorIdentity",
            actor_id,
            "denied",
            context,
            reason_code="actor_identity_not_found",
            metadata={"message": "Actor identity not found."},
        )
    raise HTTPException(status_code=404, detail="Actor identity not found.")


def _new_actor_code() -> str:
    actor_code = generate_actor_code()
    if not postgres_enabled():
        return actor_code

    while actor_authority_store.actor_code_exists(actor_code):
        actor_code = generate_actor_code()
    return actor_code


def _validate_affiliation_scope_anchor(
    *,
    organization_id: str | None,
    project_scope_id: str | None,
    action_name: str,
    target_id: str,
    context: dict[str, Any],
) -> tuple[str | None, str | None]:
    normalized_organization_id = organization_id.strip() if organization_id else None
    normalized_project_scope_id = project_scope_id.strip() if project_scope_id else None
    if not normalized_organization_id and not normalized_project_scope_id:
        _audit_actor_authority(
            action_name,
            "ActorAffiliation",
            target_id,
            "denied",
            context,
            reason_code="affiliation_scope_required",
            metadata={"message": "organizationId or projectScopeId is required."},
        )
        raise HTTPException(status_code=422, detail="organizationId or projectScopeId is required.")
    if normalized_organization_id and not (
        organization_store.organization_exists(normalized_organization_id) if postgres_enabled() else memory_store.get_organization(normalized_organization_id)
    ):
        _audit_actor_authority(
            action_name,
            "ActorAffiliation",
            target_id,
            "denied",
            context,
            reason_code="organization_not_found",
            metadata={"message": "Organization not found.", "organizationId": normalized_organization_id},
        )
        raise HTTPException(status_code=404, detail="Organization not found.")
    if normalized_project_scope_id and not (
        project_scope_store.project_scope_exists(normalized_project_scope_id) if postgres_enabled() else memory_store.get_project_scope(normalized_project_scope_id)
    ):
        _audit_actor_authority(
            action_name,
            "ActorAffiliation",
            target_id,
            "denied",
            context,
            reason_code="project_scope_not_found",
            metadata={"message": "Project scope not found.", "projectScopeId": normalized_project_scope_id},
        )
        raise HTTPException(status_code=404, detail="Project scope not found.")
    return normalized_organization_id, normalized_project_scope_id


def create_actor_identity(payload: CreateActorIdentityRequest) -> ActorIdentityResponse:
    context = meta_context(payload.meta)
    _assert_can_write_actor_authority(
        context,
        action_name="actor_identity.create",
        target_type="ActorIdentity",
        target_id="pending",
        detail="Actor is not allowed to create actor identities.",
        reason_code="forbidden_actor_identity_write",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ActorIdentityResponse(**cached)

    timestamp = memory_store.now_iso()
    actor_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "actorId": actor_id,
        "tenantId": "default",
        "actorCode": _new_actor_code(),
        "actorType": payload.actorType.value,
        "displayName": payload.displayName,
        "status": "active",
        "primaryPhone": payload.primaryPhone,
        "primaryEmail": payload.primaryEmail,
        "externalMappingsJson": payload.externalMappingsJson or {},
        "metadata": payload.metadata or {},
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    result = ActorIdentityResponse(data=_build_actor_identity_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        actor_authority_store.upsert_actor_identity(record)
        if not postgres_enabled():
            memory_store.save_actor_identity(actor_id, record)
        event = _emit_actor_authority_event(
            "actor_identity.created",
            "ActorIdentity",
            actor_id,
            record,
            context,
        )
        _audit_actor_authority("actor_identity.create", "ActorIdentity", actor_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="actor_identity.create",
            request_hash=build_request_hash(payload, extra={"action": "actor_identity.create"}),
        )

    return result


def get_actor_identity_for_actor(actor_id: str, *, meta: Meta | None) -> ActorIdentityDetail:
    context = authorize_read_surface(
        meta=meta,
        action_name="actor_identity.get",
        target_type="ActorIdentity",
        target_id=actor_id,
        allowed_roles=_ACTOR_IDENTITY_READ_ROLES,
        reason_code="forbidden_actor_identity_read",
        detail="Actor is not allowed to read actor identity details.",
    )
    return _build_actor_identity_detail(_get_actor_identity_record_or_404(actor_id, context=context))


def create_actor_affiliation(payload: CreateActorAffiliationRequest) -> ActorAffiliationResponse:
    context = meta_context(payload.meta)
    _assert_can_write_actor_authority(
        context,
        action_name="actor_affiliation.create",
        target_type="ActorAffiliation",
        target_id="pending",
        detail="Actor is not allowed to create actor affiliations.",
        reason_code="forbidden_actor_affiliation_write",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ActorAffiliationResponse(**cached)

    actor_record = _get_actor_identity_record_or_404(
        payload.actorId,
        action_name="actor_affiliation.create",
        context=context,
    )
    normalized_organization_id, normalized_project_scope_id = _validate_affiliation_scope_anchor(
        organization_id=payload.organizationId,
        project_scope_id=payload.projectScopeId,
        action_name="actor_affiliation.create",
        target_id="pending",
        context=context,
    )

    timestamp = memory_store.now_iso()
    record: dict[str, Any] = {
        "actorAffiliationId": str(uuid.uuid4()),
        "actorId": actor_record["actorId"],
        "organizationId": normalized_organization_id,
        "projectScopeId": normalized_project_scope_id,
        "affiliationKind": payload.affiliationKind.value,
        "status": "active",
        "effectiveAt": payload.effectiveAt,
        "endedAt": None,
        "confirmedBy": None,
        "confirmedAt": None,
        "metadata": payload.metadata or {},
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    result = ActorAffiliationResponse(data=_build_actor_affiliation_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        actor_authority_store.upsert_actor_affiliation(record)
        if not postgres_enabled():
            memory_store.save_actor_affiliation(record["actorAffiliationId"], record)
        event = _emit_actor_authority_event(
            "actor_affiliation.created",
            "ActorAffiliation",
            record["actorAffiliationId"],
            record,
            context,
        )
        _audit_actor_authority(
            "actor_affiliation.create",
            "ActorAffiliation",
            record["actorAffiliationId"],
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="actor_affiliation.create",
            request_hash=build_request_hash(payload, extra={"action": "actor_affiliation.create"}),
        )

    return result