"""Project cost record application service."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.gateway import check_idempotency, record_idempotency
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.project_cost_records import (
    CreateProjectCostRecordRequest,
    ProjectCostRecordDetail,
    ProjectCostRecordResponse,
)
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import project_contributions as project_contribution_store
from app.store import project_cost_records as project_cost_record_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_PROJECT_COST_RECORD_READ_ROLES = frozenset({"founder", "super_admin", "admin", "accountant"})
_PROJECT_COST_RECORD_WRITE_ROLES = frozenset({"founder", "super_admin", "admin", "accountant"})


def _build_project_cost_record_detail(record: dict[str, Any]) -> ProjectCostRecordDetail:
    return ProjectCostRecordDetail(**record)


def _audit_project_cost_record(
    action_name: str,
    cost_record_id: str,
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
        target_type="ProjectCostRecord",
        target_id=cost_record_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_project_cost_record(
    context: dict[str, Any],
    *,
    action_name: str,
    cost_record_id: str,
    detail: str,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="ProjectCostRecord",
        target_id=cost_record_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _PROJECT_COST_RECORD_WRITE_ROLES:
        return

    _audit_project_cost_record(
        action_name,
        cost_record_id,
        "denied",
        context,
        reason_code="forbidden_project_cost_record_write",
        metadata={"message": detail},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_project_scope_record_or_404(project_scope_id: str) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _get_project_contribution_record_or_404(project_contribution_event_id: str) -> dict[str, Any]:
    record = project_contribution_store.fetch_project_contribution(project_contribution_event_id) if postgres_enabled() else memory_store.get_project_contribution(project_contribution_event_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Cost source contribution not found.")


def create_project_cost_record(project_scope_id: str, payload: CreateProjectCostRecordRequest) -> ProjectCostRecordResponse:
    context = meta_context(payload.meta)
    scope = _get_project_scope_record_or_404(project_scope_id)
    _assert_can_write_project_cost_record(
        context,
        action_name="project_cost_record.record",
        cost_record_id="pending",
        detail="Actor is not allowed to record project cost records.",
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectCostRecordResponse(**cached)
    with postgres_transaction() if postgres_enabled() else nullcontext():
        contribution = _get_project_contribution_record_or_404(payload.sourceObjectId)
        if contribution.get("projectScopeId") != project_scope_id:
            raise HTTPException(status_code=404, detail="Cost source contribution not found.")
        if contribution.get("status") != "confirmed":
            raise HTTPException(status_code=422, detail="Cost source contribution must be confirmed.")

        timestamp = memory_store.now_iso()
        cost_record_id = str(uuid.uuid4())
        record = {
            "costRecordId": cost_record_id,
            "projectScopeId": project_scope_id,
            "organizationId": contribution.get("organizationId") if contribution.get("organizationId") is not None else scope["organizationId"],
            "costType": payload.costType,
            "amount": payload.amount,
            "currency": payload.currency,
            "recognizedAt": payload.recognizedAt,
            "sourceObjectType": payload.sourceObjectType,
            "sourceObjectId": payload.sourceObjectId,
            "attributionPolicy": payload.attributionPolicy,
            "metadata": payload.metadata or {},
            "createdAt": timestamp,
        }
        result = ProjectCostRecordResponse(data=_build_project_cost_record_detail(record))
        project_cost_record_store.upsert_project_cost_record(record)
        if not postgres_enabled():
            memory_store.save_project_cost_record(cost_record_id, record)
        event = events.emit(
            event_name="project_cost_record.recorded",
            aggregate_type="ProjectCostRecord",
            aggregate_id=cost_record_id,
            payload={
                "costRecordId": cost_record_id,
                "projectScopeId": project_scope_id,
                "costType": payload.costType,
                "amount": payload.amount,
                "currency": payload.currency,
                "sourceObjectType": payload.sourceObjectType,
                "sourceObjectId": payload.sourceObjectId,
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_cost_record(
            "project_cost_record.record",
            cost_record_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_cost_record.record",
            request_hash=build_request_hash(
                payload,
                extra={"action": "project_cost_record.record", "projectScopeId": project_scope_id},
            ),
        )
    return result


def list_project_cost_records_for_actor(project_scope_id: str, *, meta: Meta | None) -> list[ProjectCostRecordDetail]:
    authorize_read_surface(
        meta=meta,
        action_name="project_cost_record.list",
        target_type="ProjectCostRecord",
        target_id=project_scope_id,
        allowed_roles=_PROJECT_COST_RECORD_READ_ROLES,
        reason_code="forbidden_project_cost_record_read",
        detail="Actor is not allowed to read project cost records.",
    )
    _get_project_scope_record_or_404(project_scope_id)
    records = project_cost_record_store.list_project_cost_records(project_scope_id) if postgres_enabled() else memory_store.list_project_cost_records(project_scope_id)
    return [_build_project_cost_record_detail(record) for record in records]