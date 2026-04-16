from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_shared_resource_code
from app.core.gateway import check_idempotency, record_idempotency
from app.core.policy_sets import FOUNDATION_ADMIN_ROLES
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.shared_resources import (
    AllocateSharedResourceRequest,
    CreateSharedResourceRequest,
    ReleaseSharedResourceAllocationRequest,
    SharedResourceAllocationDetail,
    SharedResourceAllocationResponse,
    SharedResourceDetail,
    SharedResourceResponse,
    SharedResourceSummary,
)
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import project_scopes as project_scope_store
from app.store import shared_resource_allocations as shared_resource_allocation_store
from app.store import shared_resources as shared_resource_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_SHARED_RESOURCE_READ_ROLES = FOUNDATION_ADMIN_ROLES
_SHARED_RESOURCE_WRITE_ROLES = FOUNDATION_ADMIN_ROLES


def _build_shared_resource_detail(record: dict[str, Any]) -> SharedResourceDetail:
    return SharedResourceDetail(
        sharedResourceId=record["sharedResourceId"],
        organizationId=record["organizationId"],
        resourceCode=record["resourceCode"],
        name=record["name"],
        resourceType=record["resourceType"],
        status=record["status"],
        capacityValue=record.get("capacityValue"),
        capacityUnit=record.get("capacityUnit"),
        description=record.get("description"),
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _build_shared_resource_summary(record: dict[str, Any]) -> SharedResourceSummary:
    return SharedResourceSummary(
        sharedResourceId=record["sharedResourceId"],
        organizationId=record["organizationId"],
        resourceCode=record["resourceCode"],
        name=record["name"],
        resourceType=record["resourceType"],
        status=record["status"],
        capacityValue=record.get("capacityValue"),
        capacityUnit=record.get("capacityUnit"),
        createdAt=record.get("createdAt"),
    )


def _build_shared_resource_allocation_detail(record: dict[str, Any]) -> SharedResourceAllocationDetail:
    return SharedResourceAllocationDetail(
        allocationId=record["allocationId"],
        sharedResourceId=record["sharedResourceId"],
        projectScopeId=record["projectScopeId"],
        allocationBasis=record["allocationBasis"],
        allocatedCapacity=record["allocatedCapacity"],
        releasedCapacity=record["releasedCapacity"],
        status=record["status"],
        effectiveAt=record["effectiveAt"],
        releasedAt=record.get("releasedAt"),
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _emit_shared_resource_event(
    event_name: str,
    shared_resource_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="SharedResource",
        aggregate_id=shared_resource_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_shared_resource(
    action_name: str,
    shared_resource_id: str,
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
        target_type="SharedResource",
        target_id=shared_resource_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_shared_resource(
    context: dict[str, Any],
    *,
    action_name: str,
    shared_resource_id: str,
    detail: str,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="SharedResource",
        target_id=shared_resource_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _SHARED_RESOURCE_WRITE_ROLES:
        return

    _audit_shared_resource(
        action_name,
        shared_resource_id,
        "denied",
        context,
        reason_code="forbidden_shared_resource_write",
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_shared_resource_record_or_404(
    shared_resource_id: str,
    *,
    action_name: str = "shared_resource.get",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = (
        shared_resource_store.fetch_shared_resource(shared_resource_id)
        if postgres_enabled() else memory_store.get_shared_resource(shared_resource_id)
    )
    if record is not None:
        return record

    if context is not None:
        _audit_shared_resource(
            action_name,
            shared_resource_id,
            "denied",
            context,
            reason_code="shared_resource_not_found",
            metadata={"message": "Shared resource not found."},
        )
    raise HTTPException(status_code=404, detail="Shared resource not found.")


def _new_shared_resource_code() -> str:
    resource_code = generate_shared_resource_code()
    if not postgres_enabled():
        return resource_code

    while shared_resource_store.shared_resource_code_exists(resource_code):
        resource_code = generate_shared_resource_code()
    return resource_code


def _get_project_scope_record_or_404(project_scope_id: str) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _get_shared_resource_allocation_record_or_404(allocation_id: str) -> dict[str, Any]:
    record = (
        shared_resource_allocation_store.fetch_shared_resource_allocation(allocation_id)
        if postgres_enabled()
        else memory_store.get_shared_resource_allocation(allocation_id)
    )
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Shared resource allocation not found.")


def create_shared_resource(payload: CreateSharedResourceRequest) -> SharedResourceResponse:
    context = meta_context(payload.meta)
    _assert_can_write_shared_resource(
        context,
        action_name="shared_resource.create",
        shared_resource_id="pending",
        detail="Actor is not allowed to create shared resources.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return SharedResourceResponse(**cached)

    timestamp = memory_store.now_iso()
    shared_resource_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "sharedResourceId": shared_resource_id,
        "organizationId": payload.organizationId,
        "resourceCode": _new_shared_resource_code(),
        "name": payload.name,
        "resourceType": payload.resourceType.value,
        "status": "draft",
        "capacityValue": payload.capacityValue,
        "capacityUnit": payload.capacityUnit,
        "description": payload.description,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    result = SharedResourceResponse(data=_build_shared_resource_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        shared_resource_store.upsert_shared_resource(record)
        if not postgres_enabled():
            memory_store.save_shared_resource(shared_resource_id, record)
        event = _emit_shared_resource_event("shared_resource.created", shared_resource_id, payload=record, context=context)
        _audit_shared_resource(
            "shared_resource.create",
            shared_resource_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="shared_resource.create",
            request_hash=build_request_hash(payload, extra={"action": "shared_resource.create"}),
        )

    return result


def allocate_shared_resource(
    shared_resource_id: str,
    payload: AllocateSharedResourceRequest,
) -> SharedResourceAllocationResponse:
    context = meta_context(payload.meta)
    _assert_can_write_shared_resource(
        context,
        action_name="shared_resource.allocate",
        shared_resource_id=shared_resource_id,
        detail="Actor is not allowed to allocate shared resources.",
    )
    resource = _get_shared_resource_record_or_404(
        shared_resource_id,
        action_name="shared_resource.allocate",
        context=context,
    )
    project_scope = _get_project_scope_record_or_404(payload.projectScopeId)
    if resource["organizationId"] != project_scope["organizationId"]:
        raise HTTPException(status_code=409, detail="Shared resource organization does not match the target project scope.")

    allocated_capacity = float(payload.allocatedCapacity)
    total_capacity = float(resource.get("capacityValue") or 0.0)
    active_allocated_capacity = (
        shared_resource_allocation_store.get_active_shared_resource_allocated_capacity(shared_resource_id)
        if postgres_enabled()
        else memory_store.get_active_shared_resource_allocated_capacity(shared_resource_id)
    )
    if total_capacity and active_allocated_capacity + allocated_capacity > total_capacity + 0.000001:
        raise HTTPException(status_code=409, detail="Shared resource allocation exceeds available capacity.")

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return SharedResourceAllocationResponse(**cached)

    timestamp = payload.effectiveAt or memory_store.now_iso()
    allocation_id = str(uuid.uuid4())
    record = {
        "allocationId": allocation_id,
        "sharedResourceId": shared_resource_id,
        "projectScopeId": payload.projectScopeId,
        "allocationBasis": payload.allocationBasis,
        "allocatedCapacity": allocated_capacity,
        "releasedCapacity": 0.0,
        "status": "active",
        "effectiveAt": timestamp,
        "releasedAt": None,
        "createdAt": memory_store.now_iso(),
        "updatedAt": memory_store.now_iso(),
    }
    result = SharedResourceAllocationResponse(data=_build_shared_resource_allocation_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        shared_resource_allocation_store.upsert_shared_resource_allocation(record)
        if not postgres_enabled():
            memory_store.save_shared_resource_allocation(allocation_id, record)
        event = _emit_shared_resource_event(
            "shared_resource.allocated",
            shared_resource_id,
            payload={
                "allocationId": allocation_id,
                "projectScopeId": payload.projectScopeId,
                "allocationBasis": payload.allocationBasis,
                "allocatedCapacity": allocated_capacity,
                "effectiveAt": timestamp,
            },
            context=context,
        )
        _audit_shared_resource(
            "shared_resource.allocate",
            shared_resource_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="shared_resource.allocate",
            request_hash=build_request_hash(payload, extra={"action": "shared_resource.allocate", "sharedResourceId": shared_resource_id}),
        )
    return result


def release_shared_resource_allocation(
    shared_resource_id: str,
    allocation_id: str,
    payload: ReleaseSharedResourceAllocationRequest,
) -> SharedResourceAllocationResponse:
    context = meta_context(payload.meta)
    _assert_can_write_shared_resource(
        context,
        action_name="shared_resource.release",
        shared_resource_id=shared_resource_id,
        detail="Actor is not allowed to release shared resources.",
    )
    _get_shared_resource_record_or_404(shared_resource_id, action_name="shared_resource.release", context=context)
    allocation = _get_shared_resource_allocation_record_or_404(allocation_id)
    if allocation["sharedResourceId"] != shared_resource_id:
        raise HTTPException(status_code=404, detail="Shared resource allocation not found.")
    if allocation["status"] != "active":
        raise HTTPException(status_code=409, detail="Shared resource allocation is not active.")
    if float(payload.releasedCapacity) != float(allocation["allocatedCapacity"]):
        raise HTTPException(status_code=409, detail="Shared resource release must match the full allocated capacity.")

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return SharedResourceAllocationResponse(**cached)

    updated_record = {
        **allocation,
        "releasedCapacity": float(payload.releasedCapacity),
        "status": "released",
        "releasedAt": memory_store.now_iso(),
        "updatedAt": memory_store.now_iso(),
    }
    result = SharedResourceAllocationResponse(data=_build_shared_resource_allocation_detail(updated_record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        shared_resource_allocation_store.upsert_shared_resource_allocation(updated_record)
        if not postgres_enabled():
            memory_store.save_shared_resource_allocation(allocation_id, updated_record)
        event = _emit_shared_resource_event(
            "shared_resource.released",
            shared_resource_id,
            payload={
                "allocationId": allocation_id,
                "projectScopeId": allocation["projectScopeId"],
                "releasedCapacity": float(payload.releasedCapacity),
                "releasedAt": updated_record["releasedAt"],
            },
            context=context,
        )
        _audit_shared_resource(
            "shared_resource.release",
            shared_resource_id,
            "allowed",
            context,
            before_snapshot=allocation,
            after_snapshot=updated_record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="shared_resource.release",
            request_hash=build_request_hash(payload, extra={"action": "shared_resource.release", "sharedResourceId": shared_resource_id, "allocationId": allocation_id}),
        )
    return result


def list_shared_resources_for_actor(*, meta: Meta | None) -> list[SharedResourceSummary]:
    authorize_read_surface(
        meta=meta,
        action_name="shared_resource.list",
        target_type="SharedResource",
        target_id="collection",
        allowed_roles=_SHARED_RESOURCE_READ_ROLES,
        reason_code="forbidden_shared_resource_read",
        detail="Actor is not allowed to read shared resource details.",
    )
    items = shared_resource_store.list_shared_resources() if postgres_enabled() else memory_store.list_shared_resources()
    return [_build_shared_resource_summary(item) for item in items]


def get_shared_resource_for_actor(shared_resource_id: str, *, meta: Meta | None) -> SharedResourceDetail:
    context = authorize_read_surface(
        meta=meta,
        action_name="shared_resource.get",
        target_type="SharedResource",
        target_id=shared_resource_id,
        allowed_roles=_SHARED_RESOURCE_READ_ROLES,
        reason_code="forbidden_shared_resource_read",
        detail="Actor is not allowed to read shared resource details.",
    )
    return _build_shared_resource_detail(_get_shared_resource_record_or_404(shared_resource_id, context=context))