"""Project contribution application service."""

from __future__ import annotations

import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.event_registry import AggregateType, ProjectContributionEventName
from app.core.gateway import check_idempotency, record_idempotency
from app.core.policy_sets import FOUNDATION_ADMIN_ROLES
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.models.common import Meta
from app.models.enums import (
    ProjectContributionStatus,
    ProjectContributionVerificationSource,
    ProjectContributionVerificationStatus,
)
from app.models.project_contributions import (
    ConfirmProjectContributionRequest,
    ProjectContributionDetail,
    ProjectContributionResponse,
    RecordProjectContributionRequest,
    RejectProjectContributionRequest,
)
from app.services._audit_metadata import build_authority_audit_metadata
from app.services.read_authz import authorize_read_surface
from app.store import memory as memory_store
from app.store import project_assignments as project_assignment_store
from app.store import project_contributions as project_contribution_store
from app.store import project_scopes as project_scope_store
from app.store._db import is_enabled as postgres_enabled, transaction as postgres_transaction


_PROJECT_CONTRIBUTION_READ_ROLES = FOUNDATION_ADMIN_ROLES
_PROJECT_CONTRIBUTION_WRITE_ROLES = FOUNDATION_ADMIN_ROLES


def _verification_audit_metadata(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "actorId": record.get("actorId"),
        "actorType": record.get("actorType"),
        "contributionRole": record.get("role"),
        "verificationStatus": record.get("verificationStatus"),
        "verificationSource": record.get("verificationSource"),
        "verificationEvidenceRef": record.get("verificationEvidenceRef"),
    }


def _build_project_contribution_detail(record: dict[str, Any]) -> ProjectContributionDetail:
    return ProjectContributionDetail(**record)


def _audit_project_contribution(
    action_name: str,
    project_contribution_event_id: str,
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
        target_type="ProjectContributionEvent",
        target_id=project_contribution_event_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _assert_can_write_project_contribution(
    context: dict[str, Any],
    *,
    action_name: str,
    project_contribution_event_id: str,
    detail: str,
    before_snapshot: Any | None = None,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="ProjectContributionEvent",
        target_id=project_contribution_event_id,
        context=context,
    )
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role in _PROJECT_CONTRIBUTION_WRITE_ROLES:
        return

    _audit_project_contribution(
        action_name,
        project_contribution_event_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code="forbidden_project_contribution_write",
        metadata={"message": detail, **build_authority_audit_metadata(context)},
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


def _get_project_contribution_record_or_404(project_contribution_event_id: str) -> dict[str, Any]:
    record = project_contribution_store.fetch_project_contribution(project_contribution_event_id) if postgres_enabled() else memory_store.get_project_contribution(project_contribution_event_id)
    if record is not None:
        return record
    raise HTTPException(status_code=404, detail="Project contribution not found.")


def _raise_transition_conflict(project_contribution_event_id: str, detail: str) -> None:
    current_record = project_contribution_store.fetch_project_contribution(project_contribution_event_id) if postgres_enabled() else memory_store.get_project_contribution(project_contribution_event_id)
    if current_record is None:
        raise HTTPException(status_code=404, detail="Project contribution not found.")
    raise HTTPException(status_code=422, detail=detail)


def _save_memory_transition_from_proposed(
    project_contribution_event_id: str,
    updated_record: dict[str, Any],
    *,
    detail: str,
) -> None:
    # Memory mode is a local-dev/test fallback, so we keep the guard explicit here even
    # though it cannot provide the same atomic compare-and-swap guarantee as PostgreSQL.
    current_record = memory_store.get_project_contribution(project_contribution_event_id)
    if current_record is None:
        raise HTTPException(status_code=404, detail="Project contribution not found.")
    if current_record.get("status") != ProjectContributionStatus.proposed.value:
        _raise_transition_conflict(project_contribution_event_id, detail)
    memory_store.save_project_contribution(project_contribution_event_id, updated_record)


def record_project_contribution(project_scope_id: str, payload: RecordProjectContributionRequest) -> ProjectContributionResponse:
    context = meta_context(payload.meta)
    _get_project_scope_record_or_404(project_scope_id)
    _assert_can_write_project_contribution(
        context,
        action_name="project_contribution.record",
        project_contribution_event_id="pending",
        detail="Actor is not allowed to record project contributions.",
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectContributionResponse(**cached)

    assignment = _get_project_assignment_record_or_404(payload.projectAssignmentId)
    if assignment.get("projectScopeId") != project_scope_id:
        raise HTTPException(status_code=404, detail="Project assignment not found.")
    if assignment.get("targetType") != payload.subjectType.value or assignment.get("targetId") != payload.subjectId:
        raise HTTPException(status_code=422, detail="Contribution subject must match the project assignment target.")

    project_contribution_event_id = str(uuid.uuid4())
    record = {
        "projectContributionEventId": project_contribution_event_id,
        "projectScopeId": project_scope_id,
        "projectAssignmentId": payload.projectAssignmentId,
        "organizationId": payload.organizationId,
        "actorId": payload.actorId,
        "actorType": payload.actorType,
        "subjectType": payload.subjectType.value,
        "subjectId": payload.subjectId,
        "contributionType": payload.contributionType,
        "role": payload.role,
        "verificationStatus": payload.verificationStatus.value,
        "verificationSource": payload.verificationSource.value,
        "verificationNote": payload.verificationNote,
        "verificationEvidenceRef": payload.verificationEvidenceRef,
        "quantity": payload.quantity,
        "unit": payload.unit,
        "estimatedValue": payload.estimatedValue,
        "currency": payload.currency,
        "status": ProjectContributionStatus.proposed.value,
        "confirmedBy": None,
        "confirmedAt": None,
        "rejectionReason": None,
        "source": payload.source,
        "metadata": payload.metadata or {},
        "createdAt": memory_store.now_iso(),
    }
    result = ProjectContributionResponse(data=_build_project_contribution_detail(record))
    with postgres_transaction() if postgres_enabled() else nullcontext():
        project_contribution_store.upsert_project_contribution(record)
        if not postgres_enabled():
            memory_store.save_project_contribution(project_contribution_event_id, record)
        event = events.emit(
            event_name=ProjectContributionEventName.recorded,
            aggregate_type=AggregateType.project_contribution_event,
            aggregate_id=project_contribution_event_id,
            payload={
                "projectContributionEventId": project_contribution_event_id,
                "projectScopeId": project_scope_id,
                "actorId": payload.actorId,
                "actorType": payload.actorType,
                "contributionType": payload.contributionType,
                "role": payload.role,
                "quantity": payload.quantity,
                "estimatedValue": payload.estimatedValue,
                "status": ProjectContributionStatus.proposed.value,
                "verificationStatus": payload.verificationStatus.value,
                "verificationSource": payload.verificationSource.value,
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_contribution(
            "project_contribution.record",
            project_contribution_event_id,
            "allowed",
            context,
            after_snapshot=record,
            event=event,
            metadata={**build_authority_audit_metadata(context), **_verification_audit_metadata(record)},
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_contribution.record",
            request_hash=build_request_hash(
                payload,
                extra={"action": "project_contribution.record", "projectScopeId": project_scope_id},
            ),
        )

    return result


def list_project_contributions_for_actor(project_scope_id: str, *, meta: Meta | None) -> list[ProjectContributionDetail]:
    authorize_read_surface(
        meta=meta,
        action_name="project_contribution.list",
        target_type="ProjectContributionEvent",
        target_id=project_scope_id,
        allowed_roles=_PROJECT_CONTRIBUTION_READ_ROLES,
        reason_code="forbidden_project_contribution_read",
        detail="Actor is not allowed to read project contributions.",
    )
    _get_project_scope_record_or_404(project_scope_id)
    records = project_contribution_store.list_project_contributions(project_scope_id) if postgres_enabled() else memory_store.list_project_contributions(project_scope_id)
    return [_build_project_contribution_detail(record) for record in records]


def confirm_project_contribution(
    project_scope_id: str,
    project_contribution_event_id: str,
    payload: ConfirmProjectContributionRequest,
) -> ProjectContributionResponse:
    context = meta_context(payload.meta)
    record = _get_project_contribution_record_or_404(project_contribution_event_id)
    if record.get("projectScopeId") != project_scope_id:
        raise HTTPException(status_code=404, detail="Project contribution not found.")

    before_snapshot = copy.deepcopy(record)
    _assert_can_write_project_contribution(
        context,
        action_name="project_contribution.confirm",
        project_contribution_event_id=project_contribution_event_id,
        detail="Actor is not allowed to confirm project contributions.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectContributionResponse(**cached)
    if record.get("status") != ProjectContributionStatus.proposed.value:
        raise HTTPException(status_code=422, detail="Project contribution is not confirmable.")

    updated_record = {
        **record,
        "status": ProjectContributionStatus.confirmed.value,
        "confirmedBy": context.get("actor_id"),
        "confirmedAt": memory_store.now_iso(),
        "verificationStatus": ProjectContributionVerificationStatus.verified.value,
        "verificationSource": ProjectContributionVerificationSource.admin_confirmed.value,
        "verificationNote": payload.verificationNote,
        "verificationEvidenceRef": payload.verificationEvidenceRef,
    }
    persisted_record: dict[str, Any] = updated_record
    with postgres_transaction() if postgres_enabled() else nullcontext():
        if postgres_enabled():
            transitioned_record = project_contribution_store.transition_project_contribution_from_proposed(updated_record)
            if transitioned_record is None:
                _raise_transition_conflict(project_contribution_event_id, "Project contribution is not confirmable.")
            assert transitioned_record is not None
            persisted_record = transitioned_record
        else:
            _save_memory_transition_from_proposed(
                project_contribution_event_id,
                updated_record,
                detail="Project contribution is not confirmable.",
            )
        event = events.emit(
            event_name=ProjectContributionEventName.confirmed,
            aggregate_type=AggregateType.project_contribution_event,
            aggregate_id=project_contribution_event_id,
            payload={
                "projectContributionEventId": project_contribution_event_id,
                "projectScopeId": project_scope_id,
                "confirmedBy": persisted_record["confirmedBy"],
                "confirmedAt": persisted_record["confirmedAt"],
                "verificationStatus": persisted_record["verificationStatus"],
                "verificationSource": persisted_record["verificationSource"],
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_contribution(
            "project_contribution.confirm",
            project_contribution_event_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=persisted_record,
            event=event,
            metadata={
                **build_authority_audit_metadata(context),
                "verificationStatusBefore": before_snapshot.get("verificationStatus"),
                **_verification_audit_metadata(persisted_record),
            },
        )
        result = ProjectContributionResponse(data=_build_project_contribution_detail(persisted_record))
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_contribution.confirm",
            request_hash=build_request_hash(
                payload,
                extra={
                    "action": "project_contribution.confirm",
                    "projectScopeId": project_scope_id,
                    "projectContributionEventId": project_contribution_event_id,
                },
            ),
        )
    return result


def reject_project_contribution(
    project_scope_id: str,
    project_contribution_event_id: str,
    payload: RejectProjectContributionRequest,
) -> ProjectContributionResponse:
    context = meta_context(payload.meta)
    record = _get_project_contribution_record_or_404(project_contribution_event_id)
    if record.get("projectScopeId") != project_scope_id:
        raise HTTPException(status_code=404, detail="Project contribution not found.")

    before_snapshot = copy.deepcopy(record)
    _assert_can_write_project_contribution(
        context,
        action_name="project_contribution.reject",
        project_contribution_event_id=project_contribution_event_id,
        detail="Actor is not allowed to reject project contributions.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return ProjectContributionResponse(**cached)
    if record.get("status") != ProjectContributionStatus.proposed.value:
        raise HTTPException(status_code=422, detail="Project contribution is not rejectable.")

    updated_record = {
        **record,
        "status": ProjectContributionStatus.rejected.value,
        "rejectionReason": payload.reason,
        "verificationStatus": ProjectContributionVerificationStatus.rejected.value,
        "verificationSource": ProjectContributionVerificationSource.admin_rejected.value,
        "verificationNote": payload.reason,
        "verificationEvidenceRef": None,
    }
    persisted_record: dict[str, Any] = updated_record
    with postgres_transaction() if postgres_enabled() else nullcontext():
        if postgres_enabled():
            transitioned_record = project_contribution_store.transition_project_contribution_from_proposed(updated_record)
            if transitioned_record is None:
                _raise_transition_conflict(project_contribution_event_id, "Project contribution is not rejectable.")
            assert transitioned_record is not None
            persisted_record = transitioned_record
        else:
            _save_memory_transition_from_proposed(
                project_contribution_event_id,
                updated_record,
                detail="Project contribution is not rejectable.",
            )
        event = events.emit(
            event_name=ProjectContributionEventName.rejected,
            aggregate_type=AggregateType.project_contribution_event,
            aggregate_id=project_contribution_event_id,
            payload={
                "projectContributionEventId": project_contribution_event_id,
                "projectScopeId": project_scope_id,
                "reason": payload.reason,
                "verificationStatus": persisted_record["verificationStatus"],
                "verificationSource": persisted_record["verificationSource"],
            },
            actor_id=context.get("actor_id"),
            correlation_id=context.get("correlation_id"),
            causation_id=context.get("causation_id"),
            idempotency_key=context.get("idempotency_key"),
        )
        _audit_project_contribution(
            "project_contribution.reject",
            project_contribution_event_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=persisted_record,
            event=event,
            metadata={
                **build_authority_audit_metadata(context),
                "verificationStatusBefore": before_snapshot.get("verificationStatus"),
                **_verification_audit_metadata(persisted_record),
            },
        )
        result = ProjectContributionResponse(data=_build_project_contribution_detail(persisted_record))
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="project_contribution.reject",
            request_hash=build_request_hash(
                payload,
                extra={
                    "action": "project_contribution.reject",
                    "projectScopeId": project_scope_id,
                    "projectContributionEventId": project_contribution_event_id,
                },
            ),
        )
    return result