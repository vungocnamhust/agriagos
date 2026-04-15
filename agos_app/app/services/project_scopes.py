from __future__ import annotations

import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_project_scope_code
from app.core.gateway import assert_project_scope_transition, check_idempotency, record_idempotency
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.project_scopes import (
    ActivateProjectScopeRequest,
    ArchiveProjectScopeRequest,
    CloseProjectScopeRequest,
    CreateProjectScopeRequest,
    PauseProjectScopeRequest,
    ProjectScopeDetail,
    ProjectScopeResponse,
    ProjectScopeSummary,
    UpdateProjectScopeRequest,
)
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_PROJECT_SCOPE_READ_ROLES = frozenset({"founder", "super_admin", "admin"})
_PROJECT_SCOPE_WRITE_ROLES = frozenset({"founder", "super_admin", "admin"})


def _build_project_scope_detail(record: dict[str, Any]) -> ProjectScopeDetail:
    return ProjectScopeDetail(
        projectScopeId=record["projectScopeId"],
        organizationId=record["organizationId"],
        projectScopeCode=record["projectScopeCode"],
        name=record["name"],
        projectScopeType=record["projectScopeType"],
        status=record["status"],
        seasonYear=record.get("seasonYear"),
        ownerActorId=record.get("ownerActorId"),
        description=record.get("description"),
        parentProjectScopeId=record.get("parentProjectScopeId"),
        metadata=record.get("metadata"),
        createdAt=record.get("createdAt"),
        updatedAt=record.get("updatedAt"),
    )


def _build_project_scope_summary(record: dict[str, Any]) -> ProjectScopeSummary:
    return ProjectScopeSummary(
        projectScopeId=record["projectScopeId"],
        organizationId=record["organizationId"],
        projectScopeCode=record["projectScopeCode"],
        name=record["name"],
        projectScopeType=record["projectScopeType"],
        status=record["status"],
        seasonYear=record.get("seasonYear"),
        ownerActorId=record.get("ownerActorId"),
        createdAt=record.get("createdAt"),
    )


def _emit_project_scope_event(
    event_name: str,
    project_scope_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="ProjectScope",
        aggregate_id=project_scope_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_project_scope(
    action_name: str,
    project_scope_id: str,
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
        target_type="ProjectScope",
        target_id=project_scope_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_project_scope(
    context: dict[str, Any],
    *,
    action_name: str,
    project_scope_id: str,
    detail: str,
    before_snapshot: Any | None = None,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="ProjectScope",
        target_id=project_scope_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _PROJECT_SCOPE_WRITE_ROLES:
        return

    _audit_project_scope(
        action_name,
        project_scope_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code="forbidden_project_scope_write",
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_project_scope_record_or_404(
    project_scope_id: str,
    *,
    action_name: str = "project_scope.get",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record

    if context is not None:
        _audit_project_scope(
            action_name,
            project_scope_id,
            "denied",
            context,
            reason_code="project_scope_not_found",
            metadata={"message": "Project scope not found."},
        )
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _new_project_scope_code() -> str:
    project_scope_code = generate_project_scope_code()
    if not postgres_enabled():
        return project_scope_code

    while project_scope_store.project_scope_code_exists(project_scope_code):
        project_scope_code = generate_project_scope_code()
    return project_scope_code


def create_project_scope(payload: CreateProjectScopeRequest) -> ProjectScopeResponse:
    context = meta_context(payload.meta)
    _assert_can_write_project_scope(
        context,
        action_name="project_scope.create",
        project_scope_id="pending",
        detail="Actor is not allowed to create project scopes.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectScopeResponse(**cached)

    timestamp = memory_store.now_iso()
    project_scope_id = str(uuid.uuid4())
    record: dict[str, Any] = {
        "projectScopeId": project_scope_id,
        "organizationId": payload.organizationId,
        "projectScopeCode": _new_project_scope_code(),
        "name": payload.name,
        "projectScopeType": payload.projectScopeType.value,
        "status": "draft",
        "seasonYear": payload.seasonYear,
        "ownerActorId": payload.ownerActorId,
        "description": payload.description,
        "parentProjectScopeId": payload.parentProjectScopeId,
        "metadata": payload.metadata or {},
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    result = ProjectScopeResponse(data=_build_project_scope_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_scope_store.upsert_project_scope(record)
        if not postgres_enabled():
            memory_store.save_project_scope(project_scope_id, record)
        event = _emit_project_scope_event("project_scope.created", project_scope_id, payload=record, context=context)
        _audit_project_scope("project_scope.create", project_scope_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_scope.create",
            request_hash=build_request_hash(payload, extra={"action": "project_scope.create"}),
        )

    return result


def list_project_scopes_for_actor(*, meta: Meta | None) -> list[ProjectScopeSummary]:
    authorize_read_surface(
        meta=meta,
        action_name="project_scope.list",
        target_type="ProjectScope",
        target_id="collection",
        allowed_roles=_PROJECT_SCOPE_READ_ROLES,
        reason_code="forbidden_project_scope_read",
        detail="Actor is not allowed to read project scope details.",
    )
    items = project_scope_store.list_project_scopes() if postgres_enabled() else memory_store.list_project_scopes()
    return [_build_project_scope_summary(item) for item in items]


def get_project_scope_for_actor(project_scope_id: str, *, meta: Meta | None) -> ProjectScopeDetail:
    context = authorize_read_surface(
        meta=meta,
        action_name="project_scope.get",
        target_type="ProjectScope",
        target_id=project_scope_id,
        allowed_roles=_PROJECT_SCOPE_READ_ROLES,
        reason_code="forbidden_project_scope_read",
        detail="Actor is not allowed to read project scope details.",
    )
    return _build_project_scope_detail(_get_project_scope_record_or_404(project_scope_id, context=context))


def update_project_scope(project_scope_id: str, payload: UpdateProjectScopeRequest) -> ProjectScopeResponse:
    context = meta_context(payload.meta)
    record = _get_project_scope_record_or_404(project_scope_id, action_name="project_scope.update", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_project_scope(
        context,
        action_name="project_scope.update",
        project_scope_id=project_scope_id,
        detail="Actor is not allowed to update project scopes.",
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectScopeResponse(**cached)

    changed_fields: list[str] = []
    for field_name in (
        "name",
        "seasonYear",
        "ownerActorId",
        "description",
        "parentProjectScopeId",
        "metadata",
    ):
        new_value = getattr(payload, field_name)
        if new_value is None:
            continue
        record[field_name] = new_value
        changed_fields.append(field_name)

    if not changed_fields:
        _audit_project_scope(
            "project_scope.update",
            project_scope_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="empty_update_payload",
            metadata={"message": "Update payload must include at least one mutable field."},
        )
        raise HTTPException(status_code=422, detail="Update payload must include at least one mutable field.")

    record["updatedAt"] = memory_store.now_iso()
    result = ProjectScopeResponse(data=_build_project_scope_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_scope_store.upsert_project_scope(record)
        if not postgres_enabled():
            memory_store.save_project_scope(project_scope_id, record)
        event = _emit_project_scope_event(
            "project_scope.updated",
            project_scope_id,
            payload={
                "projectScopeId": project_scope_id,
                "changedFields": changed_fields,
                "afterSummary": _build_project_scope_summary(record).model_dump(),
            },
            context=context,
        )
        _audit_project_scope(
            "project_scope.update",
            project_scope_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_scope.update",
            request_hash=build_request_hash(payload, extra={"action": "project_scope.update", "projectScopeId": project_scope_id}),
        )
    return result


def _transition_project_scope(
    project_scope_id: str,
    payload: ActivateProjectScopeRequest | PauseProjectScopeRequest | CloseProjectScopeRequest | ArchiveProjectScopeRequest,
    *,
    action_name: str,
    action: str,
    denied_detail: str,
    event_name: str,
    reason: str | None = None,
) -> ProjectScopeResponse:
    context = meta_context(payload.meta)
    record = _get_project_scope_record_or_404(project_scope_id, action_name=action_name, context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_can_write_project_scope(
        context,
        action_name=action_name,
        project_scope_id=project_scope_id,
        detail=denied_detail,
        before_snapshot=before_snapshot,
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectScopeResponse(**cached)

    try:
        next_status = assert_project_scope_transition(record, action)
    except HTTPException as exc:
        _audit_project_scope(
            action_name,
            project_scope_id,
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
    result = ProjectScopeResponse(data=_build_project_scope_detail(record))
    event_payload = {
        "projectScopeId": project_scope_id,
        "oldStatus": old_status,
        "newStatus": next_status,
    }
    if reason is not None:
        event_payload["reason"] = reason

    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_scope_store.upsert_project_scope(record)
        if not postgres_enabled():
            memory_store.save_project_scope(project_scope_id, record)
        event = _emit_project_scope_event(event_name, project_scope_id, payload=event_payload, context=context)
        audit_metadata = {"reason": reason} if reason is not None else None
        _audit_project_scope(
            action_name,
            project_scope_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata=audit_metadata,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name=action_name,
            request_hash=build_request_hash(payload, extra={"action": action_name, "projectScopeId": project_scope_id}),
        )
    return result


def activate_project_scope(project_scope_id: str, payload: ActivateProjectScopeRequest) -> ProjectScopeResponse:
    return _transition_project_scope(
        project_scope_id,
        payload,
        action_name="project_scope.activate",
        action="activate",
        denied_detail="Actor is not allowed to activate project scopes.",
        event_name="project_scope.activated",
    )


def pause_project_scope(project_scope_id: str, payload: PauseProjectScopeRequest) -> ProjectScopeResponse:
    return _transition_project_scope(
        project_scope_id,
        payload,
        action_name="project_scope.pause",
        action="pause",
        denied_detail="Actor is not allowed to pause project scopes.",
        event_name="project_scope.paused",
        reason=payload.reason,
    )


def close_project_scope(project_scope_id: str, payload: CloseProjectScopeRequest) -> ProjectScopeResponse:
    return _transition_project_scope(
        project_scope_id,
        payload,
        action_name="project_scope.close",
        action="close",
        denied_detail="Actor is not allowed to close project scopes.",
        event_name="project_scope.closed",
        reason=payload.reason,
    )


def archive_project_scope(project_scope_id: str, payload: ArchiveProjectScopeRequest) -> ProjectScopeResponse:
    return _transition_project_scope(
        project_scope_id,
        payload,
        action_name="project_scope.archive",
        action="archive",
        denied_detail="Actor is not allowed to archive project scopes.",
        event_name="project_scope.archived",
    )