"""Project assignment application service."""

from __future__ import annotations

import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.gateway import check_idempotency, record_idempotency
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.enums import ProjectAssignmentTargetType
from app.models.project_assignments import (
    CreateProjectAssignmentRequest,
    EndProjectAssignmentRequest,
    ProjectAssignmentDetail,
    ProjectAssignmentResponse,
    ProjectAssignmentSummary,
)
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import project_assignments as project_assignment_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction
from app.store import farm as farm_store
from app.store import lots as lot_store
from app.store import orders as order_store
from app.store import preorders as preorder_store


_PROJECT_ASSIGNMENT_READ_ROLES = frozenset({"founder", "super_admin", "admin"})
_PROJECT_ASSIGNMENT_WRITE_ROLES = frozenset({"founder", "super_admin", "admin"})


def _build_project_assignment_detail(record: dict[str, Any]) -> ProjectAssignmentDetail:
    return ProjectAssignmentDetail(
        projectAssignmentId=record["projectAssignmentId"],
        projectScopeId=record["projectScopeId"],
        targetType=record["targetType"],
        targetId=record["targetId"],
        isPrimary=record.get("isPrimary", False),
        attributionWeight=record.get("attributionWeight"),
        createdAt=record.get("createdAt"),
        endedAt=record.get("endedAt"),
        endedReason=record.get("endedReason"),
        metadata=record.get("metadata"),
    )


def _build_project_assignment_summary(record: dict[str, Any]) -> ProjectAssignmentSummary:
    return ProjectAssignmentSummary(
        projectAssignmentId=record["projectAssignmentId"],
        projectScopeId=record["projectScopeId"],
        targetType=record["targetType"],
        targetId=record["targetId"],
        isPrimary=record.get("isPrimary", False),
        attributionWeight=record.get("attributionWeight"),
        createdAt=record.get("createdAt"),
        endedAt=record.get("endedAt"),
    )


def _audit_project_assignment(
    action_name: str,
    project_assignment_id: str,
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
        target_type="ProjectAssignment",
        target_id=project_assignment_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_project_assignment(
    context: dict[str, Any],
    *,
    action_name: str,
    project_assignment_id: str,
    detail: str,
    before_snapshot: Any | None = None,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="ProjectAssignment",
        target_id=project_assignment_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _PROJECT_ASSIGNMENT_WRITE_ROLES:
        return

    _audit_project_assignment(
        action_name,
        project_assignment_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code="forbidden_project_assignment_write",
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_project_scope_record_or_404(project_scope_id: str) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _get_project_assignment_record_or_404(project_assignment_id: str) -> dict[str, Any]:
    record = project_assignment_store.fetch_project_assignment(project_assignment_id) if postgres_enabled() else memory_store.get_project_assignment(project_assignment_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project assignment not found.")


def _get_target_record(target_type: ProjectAssignmentTargetType, target_id: str) -> dict[str, Any] | None:
    if postgres_enabled():
        if target_type is ProjectAssignmentTargetType.plot:
            return farm_store.fetch_plot(target_id)
        if target_type is ProjectAssignmentTargetType.crop_cycle:
            return farm_store.fetch_crop_cycle(target_id)
        if target_type is ProjectAssignmentTargetType.lot:
            return lot_store.fetch_lot(target_id)
        if target_type is ProjectAssignmentTargetType.preorder:
            return preorder_store.fetch_preorder(target_id)
        if target_type is ProjectAssignmentTargetType.order:
            return order_store.fetch_order(target_id)
        raise ValueError(f"Unsupported target type: {target_type}")

    if target_type is ProjectAssignmentTargetType.plot:
        return memory_store.get_plot(target_id)
    if target_type is ProjectAssignmentTargetType.crop_cycle:
        return memory_store.get_crop_cycle(target_id)
    if target_type is ProjectAssignmentTargetType.lot:
        return memory_store.get_lot(target_id)
    if target_type is ProjectAssignmentTargetType.preorder:
        return memory_store.get_preorder(target_id)
    if target_type is ProjectAssignmentTargetType.order:
        return memory_store.get_order(target_id)
    raise ValueError(f"Unsupported target type: {target_type}")


def create_project_assignment(project_scope_id: str, payload: CreateProjectAssignmentRequest) -> ProjectAssignmentResponse:
    context = meta_context(payload.meta)
    _get_project_scope_record_or_404(project_scope_id)
    _assert_can_write_project_assignment(
        context,
        action_name="project_assignment.create",
        project_assignment_id="pending",
        detail="Actor is not allowed to create project assignments.",
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectAssignmentResponse(**cached)

    target_record = _get_target_record(payload.targetType, payload.targetId)
    if target_record is None:
        _audit_project_assignment(
            "project_assignment.create",
            "pending",
            "denied",
            context,
            reason_code="project_assignment_target_not_found",
            metadata={"message": "Project assignment target not found."},
        )
        raise HTTPException(status_code=404, detail="Project assignment target not found.")

    timestamp = memory_store.now_iso()
    project_assignment_id = str(uuid.uuid4())
    record = {
        "projectAssignmentId": project_assignment_id,
        "projectScopeId": project_scope_id,
        "targetType": payload.targetType.value,
        "targetId": payload.targetId,
        "isPrimary": payload.isPrimary,
        "attributionWeight": payload.attributionWeight,
        "createdAt": timestamp,
        "endedAt": None,
        "endedReason": None,
        "metadata": payload.metadata or {},
    }
    result = ProjectAssignmentResponse(data=_build_project_assignment_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_assignment_store.upsert_project_assignment(record)
        if not postgres_enabled():
            memory_store.save_project_assignment(project_assignment_id, record)
        event = events.emit(
            event_name="project_assignment.created",
            aggregate_type="ProjectAssignment",
            aggregate_id=project_assignment_id,
            payload=record,
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_assignment(
            "project_assignment.create",
            project_assignment_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_assignment.create",
            request_hash=build_request_hash(
                payload,
                extra={"action": "project_assignment.create", "projectScopeId": project_scope_id},
            ),
        )

    return result


def list_project_assignments_for_actor(project_scope_id: str, *, meta: Meta | None) -> list[ProjectAssignmentSummary]:
    authorize_read_surface(
        meta=meta,
        action_name="project_assignment.list",
        target_type="ProjectAssignment",
        target_id=project_scope_id,
        allowed_roles=_PROJECT_ASSIGNMENT_READ_ROLES,
        reason_code="forbidden_project_assignment_read",
        detail="Actor is not allowed to read project assignments.",
    )
    _get_project_scope_record_or_404(project_scope_id)
    records = project_assignment_store.list_project_assignments(project_scope_id) if postgres_enabled() else memory_store.list_project_assignments(project_scope_id)
    return [_build_project_assignment_summary(record) for record in records]


def end_project_assignment(
    project_scope_id: str,
    project_assignment_id: str,
    payload: EndProjectAssignmentRequest,
) -> ProjectAssignmentResponse:
    context = meta_context(payload.meta)
    record = _get_project_assignment_record_or_404(project_assignment_id)
    if record.get("projectScopeId") != project_scope_id:
        raise HTTPException(status_code=404, detail="Project assignment not found.")

    before_snapshot = copy.deepcopy(record)
    _assert_can_write_project_assignment(
        context,
        action_name="project_assignment.end",
        project_assignment_id=project_assignment_id,
        detail="Actor is not allowed to end project assignments.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectAssignmentResponse(**cached)

    if record.get("endedAt") is not None:
        _audit_project_assignment(
            "project_assignment.end",
            project_assignment_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="project_assignment_already_ended",
            metadata={"message": "Project assignment is already ended."},
        )
        raise HTTPException(status_code=422, detail="Project assignment is already ended.")

    record["endedAt"] = memory_store.now_iso()
    record["endedReason"] = payload.reason
    result = ProjectAssignmentResponse(data=_build_project_assignment_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_assignment_store.upsert_project_assignment(record)
        if not postgres_enabled():
            memory_store.save_project_assignment(project_assignment_id, record)
        event = events.emit(
            event_name="project_assignment.ended",
            aggregate_type="ProjectAssignment",
            aggregate_id=project_assignment_id,
            payload={
                "projectAssignmentId": project_assignment_id,
                "projectScopeId": project_scope_id,
                "endedAt": record["endedAt"],
                "endedReason": payload.reason,
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_assignment(
            "project_assignment.end",
            project_assignment_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_assignment.end",
            request_hash=build_request_hash(
                payload,
                extra={
                    "action": "project_assignment.end",
                    "projectScopeId": project_scope_id,
                    "projectAssignmentId": project_assignment_id,
                },
            ),
        )

    return result