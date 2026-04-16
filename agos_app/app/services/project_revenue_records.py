"""Project revenue record application service."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any, NoReturn

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.event_registry import AggregateType, ProjectRevenueRecordEventName
from app.core.gateway import check_idempotency, record_idempotency
from app.core.policy_sets import PROJECT_FINANCE_ROLES
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.enums import OrderStatus
from app.models.project_revenue_records import (
    CreateProjectRevenueRecordRequest,
    ProjectRevenueRecordDetail,
    ProjectRevenueRecordResponse,
)
from app.services._audit_metadata import build_authority_audit_metadata
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import orders as order_store
from app.store import project_assignments as project_assignment_store
from app.store import project_revenue_records as project_revenue_record_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_PROJECT_REVENUE_RECORD_READ_ROLES = PROJECT_FINANCE_ROLES
_PROJECT_REVENUE_RECORD_WRITE_ROLES = PROJECT_FINANCE_ROLES


def _build_project_revenue_record_detail(record: dict[str, Any]) -> ProjectRevenueRecordDetail:
    return ProjectRevenueRecordDetail(**record)


def _audit_project_revenue_record(
    action_name: str,
    revenue_record_id: str,
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
        target_type="ProjectRevenueRecord",
        target_id=revenue_record_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_project_revenue_record(
    context: dict[str, Any],
    *,
    action_name: str,
    revenue_record_id: str,
    detail: str,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="ProjectRevenueRecord",
        target_id=revenue_record_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _PROJECT_REVENUE_RECORD_WRITE_ROLES:
        return

    _audit_project_revenue_record(
        action_name,
        revenue_record_id,
        "denied",
        context,
        reason_code="forbidden_project_revenue_record_write",
        metadata={"message": detail, **build_authority_audit_metadata(context)},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_project_scope_record_or_404(project_scope_id: str) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _get_order_record_or_404(order_id: str) -> dict[str, Any]:
    record = order_store.fetch_order(order_id) if postgres_enabled() else memory_store.get_order(order_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Revenue source order not found.")


def _get_project_revenue_record_by_source(
    project_scope_id: str,
    source_object_type: str,
    source_object_id: str,
) -> dict[str, Any] | None:
    if postgres_enabled():
        return project_revenue_record_store.fetch_project_revenue_record_by_source(
            project_scope_id,
            source_object_type,
            source_object_id,
        )
    return memory_store.find_project_revenue_record_by_source(
        project_scope_id,
        source_object_type,
        source_object_id,
    )


def _has_active_project_scope_assignment(project_scope_id: str, order_id: str) -> bool:
    assignments = (
        project_assignment_store.list_project_assignments_for_target("order", order_id)
        if postgres_enabled()
        else memory_store.list_project_assignments_for_target("order", order_id)
    )
    return any(
        assignment.get("projectScopeId") == project_scope_id and assignment.get("endedAt") is None
        for assignment in assignments
    )


def _raise_project_revenue_record_error(
    *,
    context: dict[str, Any],
    revenue_record_id: str,
    status_code: int,
    detail: str,
    reason_code: str,
    metadata: dict[str, Any] | None = None,
) -> NoReturn:
    _audit_project_revenue_record(
        "project_revenue_record.record",
        revenue_record_id,
        "denied",
        context,
        reason_code=reason_code,
        metadata={"message": detail, **build_authority_audit_metadata(context), **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def create_project_revenue_record(project_scope_id: str, payload: CreateProjectRevenueRecordRequest) -> ProjectRevenueRecordResponse:
    context = meta_context(payload.meta)
    _get_project_scope_record_or_404(project_scope_id)
    _assert_can_write_project_revenue_record(
        context,
        action_name="project_revenue_record.record",
        revenue_record_id="pending",
        detail="Actor is not allowed to record project revenue records.",
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectRevenueRecordResponse(**cached)

    if payload.grossAmount < payload.netAmount:
        _raise_project_revenue_record_error(
            context=context,
            revenue_record_id="pending",
            status_code=422,
            detail="Gross amount must be greater than or equal to net amount.",
            reason_code="project_revenue_record_invalid_amounts",
            metadata={"sourceObjectId": payload.sourceObjectId},
        )

    with postgres_transaction() if postgres_enabled() else nullcontext():
        try:
            order = _get_order_record_or_404(payload.sourceObjectId)
        except HTTPException as exc:
            _raise_project_revenue_record_error(
                context=context,
                revenue_record_id="pending",
                status_code=exc.status_code,
                detail=str(exc.detail),
                reason_code="project_revenue_record_source_not_found",
                metadata={"sourceObjectId": payload.sourceObjectId},
            )
        if order.get("status") != OrderStatus.delivered.value or order.get("deliveredAt") is None:
            _raise_project_revenue_record_error(
                context=context,
                revenue_record_id="pending",
                status_code=422,
                detail="Revenue source order must be delivered.",
                reason_code="project_revenue_record_source_undelivered",
                metadata={"sourceObjectId": payload.sourceObjectId},
            )
        if not _has_active_project_scope_assignment(project_scope_id, payload.sourceObjectId):
            _raise_project_revenue_record_error(
                context=context,
                revenue_record_id="pending",
                status_code=422,
                detail="Revenue source order must be actively assigned to the project scope.",
                reason_code="project_revenue_record_assignment_required",
                metadata={"sourceObjectId": payload.sourceObjectId},
            )
        existing = _get_project_revenue_record_by_source(
            project_scope_id,
            payload.sourceObjectType,
            payload.sourceObjectId,
        )
        if existing is not None:
            _raise_project_revenue_record_error(
                context=context,
                revenue_record_id=str(existing["revenueRecordId"]),
                status_code=409,
                detail="Revenue source order already has a revenue record for this project scope.",
                reason_code="project_revenue_record_duplicate_source",
                metadata={"sourceObjectId": payload.sourceObjectId},
            )

        revenue_record_id = str(uuid.uuid4())
        record = {
            "revenueRecordId": revenue_record_id,
            "projectScopeId": project_scope_id,
            "organizationId": order["organizationId"],
            "customerId": order["customerId"],
            "revenueType": payload.revenueType,
            "grossAmount": payload.grossAmount,
            "netAmount": payload.netAmount,
            "currency": payload.currency,
            "recognizedAt": order["deliveredAt"],
            "sourceObjectType": payload.sourceObjectType,
            "sourceObjectId": payload.sourceObjectId,
            "metadata": payload.metadata or {},
            "createdAt": memory_store.now_iso(),
        }
        result = ProjectRevenueRecordResponse(data=_build_project_revenue_record_detail(record))
        try:
            project_revenue_record_store.upsert_project_revenue_record(record)
        except IntegrityError as exc:
            if postgres_enabled():
                existing = project_revenue_record_store.fetch_project_revenue_record_by_source(
                    project_scope_id,
                    payload.sourceObjectType,
                    payload.sourceObjectId,
                )
                if existing is not None:
                    raise HTTPException(
                        status_code=409,
                        detail="Revenue source order already has a revenue record for this project scope.",
                    ) from exc
            raise
        if not postgres_enabled():
            memory_store.save_project_revenue_record(revenue_record_id, record)
        event = events.emit(
            event_name=ProjectRevenueRecordEventName.recorded,
            aggregate_type=AggregateType.project_revenue_record,
            aggregate_id=revenue_record_id,
            payload={
                "revenueRecordId": revenue_record_id,
                "projectScopeId": project_scope_id,
                "revenueType": payload.revenueType,
                "grossAmount": payload.grossAmount,
                "netAmount": payload.netAmount,
                "currency": payload.currency,
                "recognizedAt": order["deliveredAt"],
                "sourceObjectType": payload.sourceObjectType,
                "sourceObjectId": payload.sourceObjectId,
                "customerId": order["customerId"],
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_revenue_record(
            "project_revenue_record.record",
            revenue_record_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
            metadata=build_authority_audit_metadata(context),
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_revenue_record.record",
            request_hash=build_request_hash(
                payload,
                extra={"action": "project_revenue_record.record", "projectScopeId": project_scope_id},
            ),
        )
    return result


def list_project_revenue_records_for_actor(project_scope_id: str, *, meta: Meta | None) -> list[ProjectRevenueRecordDetail]:
    authorize_read_surface(
        meta=meta,
        action_name="project_revenue_record.list",
        target_type="ProjectRevenueRecord",
        target_id=project_scope_id,
        allowed_roles=_PROJECT_REVENUE_RECORD_READ_ROLES,
        reason_code="forbidden_project_revenue_record_read",
        detail="Actor is not allowed to read project revenue records.",
    )
    _get_project_scope_record_or_404(project_scope_id)
    records = (
        project_revenue_record_store.list_project_revenue_records(project_scope_id)
        if postgres_enabled()
        else memory_store.list_project_revenue_records(project_scope_id)
    )
    return [_build_project_revenue_record_detail(record) for record in records]