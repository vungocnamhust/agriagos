"""Financial allocation application service."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from typing import Any, NoReturn

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.gateway import check_idempotency, record_idempotency
from app.core.policy_sets import PROJECT_FINANCE_ROLES
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.financial_allocations import (
    CreateFinancialAllocationRequest,
    FinancialAllocationDetail,
    FinancialAllocationResponse,
)
from app.services._audit_metadata import build_authority_audit_metadata
from app.services.read_authz import authorize_read_surface
from app.store import financial_allocations as financial_allocation_store
from app.store import memory as memory_store
from app.store import project_cost_records as project_cost_record_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_FINANCIAL_ALLOCATION_READ_ROLES = PROJECT_FINANCE_ROLES
_FINANCIAL_ALLOCATION_WRITE_ROLES = PROJECT_FINANCE_ROLES


def _build_financial_allocation_detail(record: dict[str, Any]) -> FinancialAllocationDetail:
    return FinancialAllocationDetail(**record)


def _audit_financial_allocation(
    action_name: str,
    financial_allocation_id: str,
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
        target_type="FinancialAllocation",
        target_id=financial_allocation_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_financial_allocation(
    context: dict[str, Any],
    *,
    action_name: str,
    financial_allocation_id: str,
    detail: str,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="FinancialAllocation",
        target_id=financial_allocation_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _FINANCIAL_ALLOCATION_WRITE_ROLES:
        return

    _audit_financial_allocation(
        action_name,
        financial_allocation_id,
        "denied",
        context,
        reason_code="forbidden_financial_allocation_write",
        metadata={"message": detail, **build_authority_audit_metadata(context)},
    )
    raise HTTPException(status_code=403, detail=detail)


def _get_project_scope_record_or_404(project_scope_id: str) -> dict[str, Any]:
    record = project_scope_store.fetch_project_scope(project_scope_id) if postgres_enabled() else memory_store.get_project_scope(project_scope_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project scope not found.")


def _get_project_cost_record_or_404(cost_record_id: str) -> dict[str, Any]:
    record = project_cost_record_store.fetch_project_cost_record(cost_record_id) if postgres_enabled() else memory_store.get_project_cost_record(cost_record_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Financial allocation source record not found.")


def _get_financial_allocation_by_source(project_scope_id: str, source_record_type: str, source_record_id: str) -> dict[str, Any] | None:
    if postgres_enabled():
        return financial_allocation_store.fetch_financial_allocation_by_source(project_scope_id, source_record_type, source_record_id)
    return memory_store.find_financial_allocation_by_source(project_scope_id, source_record_type, source_record_id)


def _get_financial_allocation_by_source_record(source_record_type: str, source_record_id: str) -> dict[str, Any] | None:
    if postgres_enabled():
        return financial_allocation_store.fetch_financial_allocation_by_source_record(source_record_type, source_record_id)
    return memory_store.find_financial_allocation_by_source_record(source_record_type, source_record_id)


def _list_financial_allocations_by_source_record(source_record_type: str, source_record_id: str) -> list[dict[str, Any]]:
    if postgres_enabled():
        return financial_allocation_store.list_financial_allocations_by_source_record(source_record_type, source_record_id)
    return memory_store.list_financial_allocations_by_source_record(source_record_type, source_record_id)


def _raise_financial_allocation_error(
    *,
    context: dict[str, Any],
    financial_allocation_id: str,
    status_code: int,
    detail: str,
    reason_code: str,
    metadata: dict[str, Any] | None = None,
) -> NoReturn:
    _audit_financial_allocation(
        "financial_allocation.record",
        financial_allocation_id,
        "denied",
        context,
        reason_code=reason_code,
        metadata={"message": detail, **build_authority_audit_metadata(context), **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def create_financial_allocation(project_scope_id: str, payload: CreateFinancialAllocationRequest) -> FinancialAllocationResponse:
    context = meta_context(payload.meta)
    scope = _get_project_scope_record_or_404(project_scope_id)
    _assert_can_write_financial_allocation(
        context,
        action_name="financial_allocation.record",
        financial_allocation_id="pending",
        detail="Actor is not allowed to record financial allocations.",
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return FinancialAllocationResponse(**cached)

    with postgres_transaction() if postgres_enabled() else nullcontext():
        if postgres_enabled():
            financial_allocation_store.acquire_financial_allocation_source_lock(
                payload.sourceRecordType,
                payload.sourceRecordId,
            )
        try:
            source_record = _get_project_cost_record_or_404(payload.sourceRecordId)
        except HTTPException as exc:
            _raise_financial_allocation_error(
                context=context,
                financial_allocation_id="pending",
                status_code=exc.status_code,
                detail=str(exc.detail),
                reason_code="financial_allocation_source_not_found",
                metadata={"sourceRecordId": payload.sourceRecordId},
            )

        source_organization_id = source_record.get("organizationId")
        scope_organization_id = scope.get("organizationId")
        if (
            source_organization_id is not None
            and scope_organization_id is not None
            and source_organization_id != scope_organization_id
        ):
            _raise_financial_allocation_error(
                context=context,
                financial_allocation_id="pending",
                status_code=409,
                detail="Financial allocation source record organization does not match the target project scope.",
                reason_code="financial_allocation_cross_organization_source",
                metadata={
                    "sourceRecordId": payload.sourceRecordId,
                    "sourceOrganizationId": source_organization_id,
                    "projectScopeOrganizationId": scope_organization_id,
                },
            )

        existing_for_scope = _get_financial_allocation_by_source(project_scope_id, payload.sourceRecordType, payload.sourceRecordId)
        existing_for_source = _list_financial_allocations_by_source_record(payload.sourceRecordType, payload.sourceRecordId)

        if payload.allocationBasis == "manual_full":
            existing = existing_for_source[0] if existing_for_source else None
            if existing is not None:
                _raise_financial_allocation_error(
                    context=context,
                    financial_allocation_id=str(existing["financialAllocationId"]),
                    status_code=409,
                    detail="Financial allocation already exists for this source record.",
                    reason_code="financial_allocation_duplicate_source",
                    metadata={
                        "sourceRecordId": payload.sourceRecordId,
                        "existingProjectScopeId": existing.get("projectScopeId"),
                    },
                )
            allocation_weight = 1.0
        else:
            if existing_for_scope is not None:
                _raise_financial_allocation_error(
                    context=context,
                    financial_allocation_id=str(existing_for_scope["financialAllocationId"]),
                    status_code=409,
                    detail="Financial allocation already exists for this source record and project scope.",
                    reason_code="financial_allocation_duplicate_scope_source",
                    metadata={
                        "sourceRecordId": payload.sourceRecordId,
                        "projectScopeId": project_scope_id,
                    },
                )
            allocation_weight = payload.allocationWeight or 0.0
            total_weight = sum(float(item.get("allocationWeight") or 0.0) for item in existing_for_source)
            if total_weight + allocation_weight > 1.0000001:
                _raise_financial_allocation_error(
                    context=context,
                    financial_allocation_id="pending",
                    status_code=409,
                    detail="Financial allocation total weight exceeds 1.0 for this source record.",
                    reason_code="financial_allocation_weight_exceeded",
                    metadata={
                        "sourceRecordId": payload.sourceRecordId,
                        "existingTotalWeight": total_weight,
                        "requestedAllocationWeight": allocation_weight,
                    },
                )

        financial_allocation_id = str(uuid.uuid4())
        allocated_amount = round(float(source_record["amount"]) * allocation_weight, 2)
        record = {
            "financialAllocationId": financial_allocation_id,
            "projectScopeId": project_scope_id,
            "organizationId": source_record.get("organizationId") if source_record.get("organizationId") is not None else scope["organizationId"],
            "sourceRecordType": payload.sourceRecordType,
            "sourceRecordId": payload.sourceRecordId,
            "allocationBasis": payload.allocationBasis,
            "allocationWeight": allocation_weight,
            "allocatedAmount": allocated_amount,
            "currency": source_record["currency"],
            "metadata": {},
            "createdAt": memory_store.now_iso(),
        }
        result = FinancialAllocationResponse(data=_build_financial_allocation_detail(record))
        try:
            financial_allocation_store.upsert_financial_allocation(record)
        except IntegrityError:
            existing = _get_financial_allocation_by_source(project_scope_id, payload.sourceRecordType, payload.sourceRecordId)
            _raise_financial_allocation_error(
                context=context,
                financial_allocation_id=(str(existing["financialAllocationId"]) if existing is not None else financial_allocation_id),
                status_code=409,
                detail="Financial allocation already exists for this source record and project scope.",
                reason_code="financial_allocation_duplicate_scope_source",
                metadata={
                    "sourceRecordId": payload.sourceRecordId,
                    "existingProjectScopeId": existing.get("projectScopeId") if existing is not None else project_scope_id,
                },
            )
        if not postgres_enabled():
            memory_store.save_financial_allocation(financial_allocation_id, record)
        event = events.emit(
            event_name="financial_allocation.recorded",
            aggregate_type="FinancialAllocation",
            aggregate_id=financial_allocation_id,
            payload={
                "financialAllocationId": financial_allocation_id,
                "sourceRecordType": payload.sourceRecordType,
                "sourceRecordId": payload.sourceRecordId,
                "projectScopeId": project_scope_id,
                "allocationBasis": payload.allocationBasis,
                "allocationWeight": allocation_weight,
                "allocatedAmount": allocated_amount,
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_financial_allocation(
            "financial_allocation.record",
            financial_allocation_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
            metadata=build_authority_audit_metadata(context),
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="financial_allocation.record",
            request_hash=build_request_hash(
                payload,
                extra={"action": "financial_allocation.record", "projectScopeId": project_scope_id},
            ),
        )
    return result


def list_financial_allocations_for_actor(project_scope_id: str, *, meta: Meta | None) -> list[FinancialAllocationDetail]:
    authorize_read_surface(
        meta=meta,
        action_name="financial_allocation.list",
        target_type="FinancialAllocation",
        target_id=project_scope_id,
        allowed_roles=_FINANCIAL_ALLOCATION_READ_ROLES,
        reason_code="forbidden_financial_allocation_read",
        detail="Actor is not allowed to read financial allocations.",
    )
    _get_project_scope_record_or_404(project_scope_id)
    records = financial_allocation_store.list_financial_allocations(project_scope_id) if postgres_enabled() else memory_store.list_financial_allocations(project_scope_id)
    return [_build_financial_allocation_detail(record) for record in records]