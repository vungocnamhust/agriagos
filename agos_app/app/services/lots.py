import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.codegen import generate_lot_code
from app.core.policy_sets import LOT_OPERATIONS_ROLES, LOT_QC_ROLES
from app.core.write_context import build_request_hash, meta_context
from app.core.gateway import assert_lot_transition, check_idempotency, record_idempotency
from app.models.common import Meta
from app.models.enums import LotStatus
from app.models.lots import (
    AddLotEvidenceRequest,
    AdjustLotQuantityRequest,
    BlockLotRequest,
    CreateHarvestedLotRequest,
    CreateProcessedLotRequest,
    CreateQCReviewRequest,
    LotDetail,
    LotEvidenceItem,
    LotEvidenceListResponse,
    LotEvidenceResponse,
    LotResponse,
    QCReviewItem,
    QCReviewListResponse,
    QCReviewResponse,
    ReleaseLotRequest,
    UnblockLotRequest,
)
from app.models.project_assignments import ProjectAssignmentSummary
from app.services import audit as audit_service
from app.services.read_authz import authorize_read_surface
from app.store import farm as farm_store
from app.store import organizations as organization_store
from app.store.lots import (
    append_lot_evidence,
    create_lot_evidence,
    create_qc_review_with_lot_status,
    list_lot_evidence,
    list_qc_reviews,
)
from app.store import postgres_sync
from app.store import memory as store
from app.store import project_assignments as project_assignment_store
from app.store._db import transaction as postgres_transaction


VALID_EVIDENCE_TYPES = {"photo", "video", "checklist", "note", "document", "measurement"}
VALID_QC_RESULTS = {"pending", "passed", "failed", "needs_more_evidence"}
STANDARD_LOT_UNIT = "kg"
SENSITIVE_RELEASE_ROLES = {"farm_manager", "ops", "ops_manager"}
APPROVAL_BYPASS_ROLES = {"admin", "founder", "super_admin", "admin_van_hanh"}
_LOT_READ_ROLES = LOT_QC_ROLES
_LOT_CREATE_ROLES = LOT_OPERATIONS_ROLES
_LOT_STATE_WRITE_ROLES = LOT_OPERATIONS_ROLES
_LOT_EVIDENCE_WRITE_ROLES = LOT_QC_ROLES
_LOT_QC_WRITE_ROLES = LOT_QC_ROLES


def _effective_lot_actor_role(context: dict[str, Any], *, allow_delegated_agent: bool = False) -> str | None:
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role != "agent" or not allow_delegated_agent:
        return actor_role

    delegated_actor_role = normalize_actor_role(context.get("delegated_actor_role"))
    return delegated_actor_role or actor_role


def _assert_lot_access(
    *,
    context: dict[str, Any],
    action_name: str,
    lot_id: str,
    allowed_roles: frozenset[str],
    reason_code: str,
    detail: str,
    before_snapshot: Any | None = None,
    allow_delegated_agent: bool = False,
) -> None:
    ensure_bypass_permitted(
        action_name=action_name,
        target_type="Lot",
        target_id=lot_id,
        context=context,
    )

    actor_role = _effective_lot_actor_role(context, allow_delegated_agent=allow_delegated_agent)
    if actor_role in allowed_roles:
        return

    _audit_lot(
        action_name,
        lot_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, "effectiveActorRole": actor_role},
    )
    raise HTTPException(status_code=403, detail=detail)


def _new_lot_code(product_sku_id: str) -> str:
    # Use first 3 chars of the SKU id as the abbreviation; Phase 2 will use a proper SKU abbr field
    sku_abbr = product_sku_id[:3].upper()
    return generate_lot_code(sku_abbr)


def _build_lot_detail(record: dict[str, Any]) -> LotDetail:
    assignments = _list_assignment_summaries("lot", record["lotId"])
    return LotDetail(
        lotId=record["lotId"],
        lotCode=record["lotCode"],
        organizationId=record.get("organizationId"),
        productSkuId=record["productSkuId"],
        sourceType=record["sourceType"],
        sourceRefId=record["sourceRefId"],
        harvestOrProductionDate=record["harvestOrProductionDate"],
        actualQty=record["actualQty"],
        availableQty=record["availableQty"],
        reservedQty=record["reservedQty"],
        releasedQty=record["releasedQty"],
        unit=record.get("unit", STANDARD_LOT_UNIT),
        status=record["status"],
        assignments=assignments,
    )


def _list_assignment_summaries(target_type: str, target_id: str) -> list[ProjectAssignmentSummary]:
    records = (
        project_assignment_store.list_project_assignments_for_target(target_type, target_id)
        if postgres_sync.is_enabled()
        else store.list_project_assignments_for_target(target_type, target_id)
    )
    return [ProjectAssignmentSummary(**record) for record in records]


def _normalize_unit(unit: str | None) -> str:
    normalized = (unit or STANDARD_LOT_UNIT).strip().lower()
    if normalized != STANDARD_LOT_UNIT:
        raise HTTPException(status_code=422, detail="Unsupported lot unit.")
    return normalized


def _validate_quantity(value: float) -> None:
    if value <= 0:
        raise HTTPException(status_code=422, detail="actualQty must be greater than 0.")


def _list_qc_reviews_for_lot(lot_id: str) -> list[dict[str, Any]]:
    if postgres_sync.is_enabled():
        return list_qc_reviews(lot_id)
    return store.get_lot_qc_reviews(lot_id)


def _latest_qc_result(lot_id: str) -> str | None:
    reviews = _list_qc_reviews_for_lot(lot_id)
    if not reviews:
        return None
    return reviews[0].get("result")


def _compute_available_qty(released_qty: float, reserved_qty: float) -> float:
    return max(released_qty - reserved_qty, 0.0)


def _requires_sensitive_release_approval(record: dict[str, Any], context: dict[str, Any]) -> bool:
    if record.get("status") != LotStatus.harvested.value:
        return False
    actor_role = context.get("actor_role")
    return actor_role in SENSITIVE_RELEASE_ROLES and actor_role not in APPROVAL_BYPASS_ROLES


def _crop_cycle_exists(crop_cycle_id: str) -> bool:
    if postgres_sync.is_enabled():
        return farm_store.fetch_crop_cycle(crop_cycle_id) is not None
    return any(cycle.get("cropCycleId") == crop_cycle_id for cycle in store.list_crop_cycles())


def _organization_exists(organization_id: str) -> bool:
    if postgres_sync.is_enabled():
        return organization_store.organization_exists(organization_id)
    return store.get_organization(organization_id) is not None


def _resolve_crop_cycle_organization_id(crop_cycle_id: str) -> str | None:
    if postgres_sync.is_enabled():
        record = farm_store.fetch_crop_cycle(crop_cycle_id)
    else:
        record = next(
            (cycle for cycle in store.list_crop_cycles() if cycle.get("cropCycleId") == crop_cycle_id),
            None,
        )
    if record is None:
        return None
    value = record.get("organizationId")
    return str(value) if value is not None else None


def _validate_harvested_lot_source(source_type: str, source_ref_id: str) -> None:
    if source_type != "crop_cycle":
        raise HTTPException(status_code=422, detail="Unsupported sourceType.")
    if not source_ref_id.strip():
        raise HTTPException(status_code=422, detail="sourceRefId is required.")
    if not _crop_cycle_exists(source_ref_id):
        raise HTTPException(status_code=422, detail="Referenced crop cycle was not found.")


def _validate_processed_lot_source(process_ref_id: str) -> None:
    if not process_ref_id.strip():
        raise HTTPException(status_code=422, detail="processRefId is required.")


def _validate_organization_id(organization_id: str | None) -> str | None:
    if organization_id is None:
        return None
    normalized = organization_id.strip()
    if not normalized:
        raise HTTPException(status_code=422, detail="organizationId cannot be blank.")
    if not _organization_exists(normalized):
        raise HTTPException(status_code=422, detail="Referenced organization was not found.")
    return normalized


def _determine_initial_status(payload: CreateHarvestedLotRequest) -> str:
    if payload.requiresQc:
        return LotStatus.qc_pending.value
    return LotStatus.harvested.value


def _create_lot_record(
    *,
    organization_id: str | None,
    product_sku_id: str,
    source_type: str,
    source_ref_id: str,
    actual_qty: float,
    unit: str,
    harvest_or_production_date: str,
    quality_note: str | None,
    attachments: list[str],
    status: str,
) -> dict[str, Any]:
    lot_id = str(uuid.uuid4())
    return {
        "lotId": lot_id,
        "tenantId": "default",
        "lotCode": _new_lot_code(product_sku_id),
        "organizationId": organization_id,
        "productSkuId": product_sku_id,
        "sourceType": source_type,
        "sourceRefId": source_ref_id,
        "harvestOrProductionDate": harvest_or_production_date,
        "actualQty": actual_qty,
        "availableQty": 0.0,
        "reservedQty": 0.0,
        "releasedQty": 0.0,
        "unit": unit,
        "qualityNote": quality_note,
        "attachments": list(attachments),
        "status": status,
    }


def _persist_created_lot(
    *,
    record: dict[str, Any],
    event_name: str,
    action_name: str,
    operation_name: str,
    context: dict[str, Any],
    request_payload: Any,
) -> LotResponse:
    actor_id = context["actor_id"]
    result = LotResponse(data=_build_lot_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            postgres_sync.upsert_lot(record)
            append_lot_evidence(record["lotId"], record["attachments"], actor_id)
        event = _emit_lot_event(
            event_name,
            record["lotId"],
            payload=record,
            context=context,
        )
        _audit_lot(action_name, record["lotId"], "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            context["idempotency_key"],
            result.model_dump(),
            operation_name=operation_name,
            request_hash=build_request_hash(request_payload, extra={"action": operation_name}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(record["lotId"], record)
    return result


def _build_lot_evidence_item(record: dict[str, Any]) -> LotEvidenceItem:
    return LotEvidenceItem(**record)


def _build_qc_review_item(record: dict[str, Any]) -> QCReviewItem:
    return QCReviewItem(**record)


def _emit_lot_event(
    event_name: str,
    lot_id: str,
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    return events.emit(
        event_name=event_name,
        aggregate_type="Lot",
        aggregate_id=lot_id,
        payload=payload,
        actor_id=context.get("actor_id"),
        correlation_id=context.get("correlation_id"),
        causation_id=context.get("causation_id"),
        idempotency_key=context.get("idempotency_key"),
    )


def _audit_lot(
    action_name: str,
    lot_id: str,
    decision: str,
    context: dict[str, Any],
    *,
    before_snapshot: Any | None = None,
    after_snapshot: Any | None = None,
    reason_code: str | None = None,
    event: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    audit_service.append_domain_audit_decision(
        action_name=action_name,
        target_type="Lot",
        target_id=lot_id,
        decision=decision,
        context=context,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        reason_code=reason_code,
        event=event,
        metadata=metadata,
    )


def _raise_lot_denied(
    *,
    action_name: str,
    lot_id: str,
    context: dict[str, Any],
    detail: str,
    reason_code: str,
    status_code: int = 422,
    before_snapshot: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _audit_lot(
        action_name,
        lot_id,
        "denied",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _raise_lot_escalated(
    *,
    action_name: str,
    lot_id: str,
    context: dict[str, Any],
    detail: str,
    reason_code: str,
    status_code: int = 403,
    before_snapshot: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _audit_lot(
        action_name,
        lot_id,
        "escalated",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _raise_lot_failed(
    *,
    action_name: str,
    lot_id: str,
    context: dict[str, Any],
    detail: str,
    reason_code: str,
    status_code: int = 500,
    before_snapshot: Any | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    _audit_lot(
        action_name,
        lot_id,
        "failed",
        context,
        before_snapshot=before_snapshot,
        reason_code=reason_code,
        metadata={"message": detail, **(metadata or {})},
    )
    raise HTTPException(status_code=status_code, detail=detail)


def _get_lot_record_or_404(
    lot_id: str,
    *,
    action_name: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_lot(lot_id)
    else:
        record = store.get_lot(lot_id)

    if not record:
        if action_name and context is not None:
            _audit_lot(
                action_name,
                lot_id,
                "denied",
                context,
                reason_code="lot_not_found",
                metadata={"message": "Lot not found."},
            )
        raise HTTPException(status_code=404, detail="Lot not found.")
    return record


def create_harvested_lot(payload: CreateHarvestedLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    _assert_lot_access(
        context=context,
        action_name="lot.create",
        lot_id=f"pending:{payload.sourceType}:{payload.sourceRefId}",
        allowed_roles=_LOT_CREATE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to create harvested lots.",
    )
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    try:
        _validate_quantity(payload.actualQty)
        _validate_harvested_lot_source(payload.sourceType, payload.sourceRefId)
        unit = _normalize_unit(payload.unit)
        initial_status = _determine_initial_status(payload)
        organization_id = _resolve_crop_cycle_organization_id(payload.sourceRefId)
    except HTTPException as exc:
        reason_code = "invalid_quantity"
        if exc.detail == "Unsupported sourceType.":
            reason_code = "invalid_source_type"
        elif exc.detail == "sourceRefId is required.":
            reason_code = "invalid_source_ref"
        elif exc.detail == "Referenced crop cycle was not found.":
            reason_code = "source_ref_not_found"
        elif exc.detail == "Unsupported lot unit.":
            reason_code = "invalid_unit"
        _audit_lot(
            "lot.create",
            f"pending:{payload.sourceType}:{payload.sourceRefId}",
            "denied",
            context,
            reason_code=reason_code,
            metadata={"message": str(exc.detail)},
        )
        raise

    record = _create_lot_record(
        organization_id=organization_id,
        product_sku_id=payload.productSkuId,
        source_type=payload.sourceType,
        source_ref_id=payload.sourceRefId,
        actual_qty=payload.actualQty,
        unit=unit,
        harvest_or_production_date=payload.harvestOrProductionDate,
        quality_note=payload.qualityNote,
        attachments=payload.attachments,
        status=initial_status,
    )
    return _persist_created_lot(
        record=record,
        event_name="lot.harvest.created",
        action_name="lot.create",
        operation_name="lot.create",
        context=context,
        request_payload=payload,
    )


def create_processed_lot(payload: CreateProcessedLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    _assert_lot_access(
        context=context,
        action_name="lot.processed_create",
        lot_id=f"pending:processing_batch:{payload.processRefId}",
        allowed_roles=_LOT_CREATE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to create processed lots.",
    )
    if cached := check_idempotency(context["idempotency_key"]):
        return LotResponse(**cached)

    try:
        _validate_quantity(payload.actualQty)
        _validate_processed_lot_source(payload.processRefId)
        unit = _normalize_unit(payload.unit)
        status = LotStatus.qc_pending.value if payload.requiresQc else LotStatus.harvested.value
        organization_id = _validate_organization_id(payload.organizationId)
    except HTTPException as exc:
        reason_code = "invalid_quantity"
        if exc.detail == "processRefId is required.":
            reason_code = "invalid_source_ref"
        elif exc.detail == "Unsupported lot unit.":
            reason_code = "invalid_unit"
        elif exc.detail == "organizationId cannot be blank.":
            reason_code = "invalid_organization_ref"
        elif exc.detail == "Referenced organization was not found.":
            reason_code = "organization_not_found"
        _audit_lot(
            "lot.processed_create",
            f"pending:processing_batch:{payload.processRefId}",
            "denied",
            context,
            reason_code=reason_code,
            metadata={"message": str(exc.detail)},
        )
        raise

    record = _create_lot_record(
        organization_id=organization_id,
        product_sku_id=payload.productSkuId,
        source_type="processing_batch",
        source_ref_id=payload.processRefId,
        actual_qty=payload.actualQty,
        unit=unit,
        harvest_or_production_date=payload.harvestOrProductionDate,
        quality_note=payload.qualityNote,
        attachments=payload.attachments,
        status=status,
    )
    return _persist_created_lot(
        record=record,
        event_name="lot.processed.created",
        action_name="lot.processed_create",
        operation_name="lot.processed_create",
        context=context,
        request_payload=payload,
    )


def adjust_lot_quantity(lot_id: str, payload: AdjustLotQuantityRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.adjust_quantity", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_lot_access(
        context=context,
        action_name="lot.adjust_quantity",
        lot_id=lot_id,
        allowed_roles=_LOT_STATE_WRITE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to adjust lot quantities.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    if payload.newActualQty <= 0:
        _audit_lot(
            "lot.adjust_quantity",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="invalid_quantity",
            metadata={"message": "newActualQty must be greater than 0."},
        )
        raise HTTPException(status_code=422, detail="newActualQty must be greater than 0.")
    if payload.newActualQty < record.get("releasedQty", 0):
        _audit_lot(
            "lot.adjust_quantity",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="adjusted_qty_below_released_qty",
            metadata={"message": "newActualQty cannot be less than releasedQty."},
        )
        raise HTTPException(status_code=422, detail="newActualQty cannot be less than releasedQty.")

    record["actualQty"] = payload.newActualQty
    result = LotResponse(data=_build_lot_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            postgres_sync.upsert_lot(record)
        event = _emit_lot_event(
            "lot.adjusted",
            lot_id,
            payload={
                "lotId": lot_id,
                "oldActualQty": before_snapshot["actualQty"],
                "newActualQty": payload.newActualQty,
                "reason": payload.reason,
            },
            context=context,
        )
        _audit_lot(
            "lot.adjust_quantity",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.adjust_quantity",
            request_hash=build_request_hash(payload, extra={"action": "lot.adjust_quantity", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, record)
    return result


def get_lot(lot_id: str, meta: Meta | None = None) -> LotDetail:
    authorize_read_surface(
        meta=meta,
        action_name="lot.get",
        target_type="Lot",
        target_id=lot_id,
        allowed_roles=_LOT_READ_ROLES,
        reason_code="forbidden_lot_read",
        detail="Actor is not allowed to read raw lot details.",
        allow_delegated_agent=False,
    )
    return _build_lot_detail(_get_lot_record_or_404(lot_id))


def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.release", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_lot_access(
        context=context,
        action_name="lot.release",
        lot_id=lot_id,
        allowed_roles=_LOT_STATE_WRITE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to release lots.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    try:
        next_status = assert_lot_transition(record, "release")
    except HTTPException as exc:
        _audit_lot(
            "lot.release",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    if payload.releasedQty <= 0:
        _raise_lot_denied(
            action_name="lot.release",
            lot_id=lot_id,
            context=context,
            detail="releasedQty must be greater than 0.",
            reason_code="invalid_released_quantity",
            before_snapshot=before_snapshot,
        )

    if payload.releasedQty > record["actualQty"]:
        _raise_lot_denied(
            action_name="lot.release",
            lot_id=lot_id,
            context=context,
            detail=f"releasedQty ({payload.releasedQty}) exceeds actualQty ({record['actualQty']}).",
            reason_code="released_qty_exceeds_actual",
            before_snapshot=before_snapshot,
        )

    reserved_qty = float(record.get("reservedQty", 0.0))
    if payload.releasedQty < reserved_qty:
        _raise_lot_denied(
            action_name="lot.release",
            lot_id=lot_id,
            context=context,
            detail=f"releasedQty ({payload.releasedQty}) cannot be less than reservedQty ({reserved_qty}).",
            reason_code="released_qty_below_reserved",
            before_snapshot=before_snapshot,
        )

    if _requires_sensitive_release_approval(record, context) and not payload.approvalRef:
        _raise_lot_escalated(
            action_name="lot.release",
            lot_id=lot_id,
            context=context,
            detail="Sensitive lot release requires approvalRef.",
            reason_code="approval_required",
            status_code=403,
            before_snapshot=before_snapshot,
            metadata={
                "requiredApprovalRef": True,
                "requiredApproverRoles": ["admin", "founder", "super_admin", "admin_van_hanh"],
                "escalationOwner": "operations_admin",
            },
        )

    if record["status"] == LotStatus.qc_pending.value and _latest_qc_result(lot_id) != "passed":
        _raise_lot_denied(
            action_name="lot.release",
            lot_id=lot_id,
            context=context,
            detail="Lot requires a passed QC review before release.",
            reason_code="qc_release_guard_failed",
            before_snapshot=before_snapshot,
        )

    if not postgres_sync.is_enabled():
        record["status"] = next_status
        record["releasedQty"] = payload.releasedQty
        record["availableQty"] = _compute_available_qty(payload.releasedQty, reserved_qty)
        if payload.qualityStatus:
            record["qualityStatus"] = payload.qualityStatus
    result_record: dict[str, Any] = record
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            persisted = postgres_sync.release_lot_atomic(
                lot_id,
                next_status=next_status,
                released_qty=payload.releasedQty,
                expected_version=record.get("version"),
            )
            if persisted is None:
                _raise_lot_failed(
                    action_name="lot.release",
                    lot_id=lot_id,
                    context=context,
                    detail="Failed to persist lot release.",
                    reason_code="persistence_failed",
                    before_snapshot=before_snapshot,
                    metadata={"failureStage": "release_lot_atomic"},
                )
            assert persisted is not None
            result_record = persisted
        event = _emit_lot_event(
            "lot.released",
            lot_id,
            payload={
                "lotId": lot_id,
                "releasedQty": result_record["releasedQty"],
                "availableQty": result_record["availableQty"],
                "reservedQty": result_record["reservedQty"],
                "status": next_status,
                "approvalRef": payload.approvalRef,
            },
            context=context,
        )
        result = LotResponse(data=_build_lot_detail(result_record))
        _audit_lot(
            "lot.release",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=result_record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.release",
            request_hash=build_request_hash(payload, extra={"action": "lot.release", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, result_record)
    return result


def block_lot(lot_id: str, payload: BlockLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.block", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_lot_access(
        context=context,
        action_name="lot.block",
        lot_id=lot_id,
        allowed_roles=_LOT_STATE_WRITE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to block lots.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    try:
        next_status = assert_lot_transition(record, "block")
    except HTTPException as exc:
        _audit_lot(
            "lot.block",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise
    if not postgres_sync.is_enabled():
        record["status"] = next_status
        record["blockReason"] = payload.reason
        record["releasedQty"] = float(record.get("reservedQty", 0.0))
        record["availableQty"] = 0.0
    result_record = record
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            persisted = postgres_sync.block_lot_atomic(lot_id, next_status=next_status, expected_version=record.get("version"))
            if persisted is None:
                raise HTTPException(status_code=500, detail="Failed to persist lot block.")
            result_record = persisted
        event = _emit_lot_event(
            "lot.blocked",
            lot_id,
            payload={
                "lotId": lot_id,
                "reason": payload.reason,
                "releasedQty": result_record["releasedQty"],
                "availableQty": result_record["availableQty"],
                "reservedQty": result_record["reservedQty"],
                "status": next_status,
            },
            context=context,
        )
        result = LotResponse(data=_build_lot_detail(result_record))
        _audit_lot(
            "lot.block",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=result_record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.block",
            request_hash=build_request_hash(payload, extra={"action": "lot.block", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, result_record)
    return result


def unblock_lot(lot_id: str, payload: UnblockLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.unblock", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_lot_access(
        context=context,
        action_name="lot.unblock",
        lot_id=lot_id,
        allowed_roles=_LOT_STATE_WRITE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to unblock lots.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    try:
        next_status = assert_lot_transition(record, "unblock")
    except HTTPException as exc:
        _audit_lot(
            "lot.unblock",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="state_transition_rejected",
            metadata={"message": str(exc.detail)},
        )
        raise

    if not postgres_sync.is_enabled():
        record["status"] = next_status
        record["unblockReason"] = payload.reason
        record["releasedQty"] = float(record.get("reservedQty", 0.0))
        record["availableQty"] = 0.0
    result_record = record
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            persisted = postgres_sync.unblock_lot_atomic(lot_id, next_status=next_status, expected_version=record.get("version"))
            if persisted is None:
                raise HTTPException(status_code=500, detail="Failed to persist lot unblock.")
            result_record = persisted
        event = _emit_lot_event(
            "lot.unblocked",
            lot_id,
            payload={
                "lotId": lot_id,
                "reason": payload.reason,
                "releasedQty": result_record["releasedQty"],
                "availableQty": result_record["availableQty"],
                "reservedQty": result_record["reservedQty"],
                "status": next_status,
            },
            context=context,
        )
        result = LotResponse(data=_build_lot_detail(result_record))
        _audit_lot(
            "lot.unblock",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=result_record,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.unblock",
            request_hash=build_request_hash(payload, extra={"action": "lot.unblock", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, result_record)
    return result


def add_lot_evidence(lot_id: str, payload: AddLotEvidenceRequest) -> LotEvidenceResponse:
    context = meta_context(payload.meta)
    lot = _get_lot_record_or_404(lot_id, action_name="lot.evidence_add", context=context)
    before_snapshot = copy.deepcopy(lot)
    _assert_lot_access(
        context=context,
        action_name="lot.evidence_add",
        lot_id=lot_id,
        allowed_roles=_LOT_EVIDENCE_WRITE_ROLES,
        reason_code="forbidden_lot_write",
        detail="Actor is not allowed to add lot evidence.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotEvidenceResponse(**cached)

    if payload.evidenceType not in VALID_EVIDENCE_TYPES:
        _audit_lot(
            "lot.evidence_add",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="unsupported_evidence_type",
            metadata={"message": "Unsupported evidenceType."},
        )
        raise HTTPException(status_code=422, detail="Unsupported evidenceType.")
    if not payload.objectStorageKey and not payload.textValue:
        _audit_lot(
            "lot.evidence_add",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="evidence_payload_missing",
            metadata={"message": "Evidence requires objectStorageKey or textValue."},
        )
        raise HTTPException(status_code=422, detail="Evidence requires objectStorageKey or textValue.")

    actor_id = context["actor_id"]
    evidence_record = {
        "tenantId": lot.get("tenantId", "default"),
        "evidenceType": payload.evidenceType,
        "objectStorageKey": payload.objectStorageKey,
        "textValue": payload.textValue,
        "actorId": actor_id,
        "status": "active",
    }

    if postgres_sync.is_enabled():
        with postgres_transaction():
            persisted = create_lot_evidence(lot_id, evidence_record)
            if persisted is None:
                raise HTTPException(status_code=500, detail="Failed to persist lot evidence.")
            event = _emit_lot_event(
                "lot.evidence.added",
                lot_id,
                payload={
                    "lotId": lot_id,
                    "evidenceType": payload.evidenceType,
                    "objectStorageKey": payload.objectStorageKey,
                    "hasTextValue": bool(payload.textValue),
                },
                context=context,
            )
            result = LotEvidenceResponse(data=_build_lot_evidence_item(persisted))
            _audit_lot(
                "lot.evidence_add",
                lot_id,
                "allowed",
                context,
                before_snapshot=before_snapshot,
                after_snapshot=persisted,
                event=event,
            )
            record_idempotency(
                key,
                result.model_dump(),
                operation_name="lot.evidence_add",
                request_hash=build_request_hash(payload, extra={"action": "lot.evidence_add", "lotId": lot_id}),
            )
    else:
        persisted = None
        memory_evidence = store.get_or_create_lot(lot_id, lot)
        evidence_items = list(memory_evidence.get("evidence", []))
        evidence_items.append(
            {
                "lotEvidenceId": str(uuid.uuid4()),
                "lotId": lot_id,
                "evidenceType": payload.evidenceType,
                "objectStorageKey": payload.objectStorageKey,
                "textValue": payload.textValue,
                "capturedAt": store.now_iso(),
                "actorId": actor_id,
                "status": "active",
            }
        )
        store.save_lot_evidence(lot_id, evidence_items)
        persisted = evidence_items[-1]
        event = _emit_lot_event(
            "lot.evidence.added",
            lot_id,
            payload={
                "lotId": lot_id,
                "evidenceType": payload.evidenceType,
                "objectStorageKey": payload.objectStorageKey,
                "hasTextValue": bool(payload.textValue),
            },
            context=context,
        )
        result = LotEvidenceResponse(data=_build_lot_evidence_item(persisted))
        _audit_lot(
            "lot.evidence_add",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=persisted,
            event=event,
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.evidence_add",
            request_hash=build_request_hash(payload, extra={"action": "lot.evidence_add", "lotId": lot_id}),
        )
    return result


def get_lot_evidence(lot_id: str, meta: Meta | None = None) -> LotEvidenceListResponse:
    authorize_read_surface(
        meta=meta,
        action_name="lot.evidence.list",
        target_type="Lot",
        target_id=lot_id,
        allowed_roles=_LOT_READ_ROLES,
        reason_code="forbidden_lot_read",
        detail="Actor is not allowed to read raw lot evidence.",
        allow_delegated_agent=False,
    )
    _get_lot_record_or_404(lot_id)
    if postgres_sync.is_enabled():
        evidence_items = list_lot_evidence(lot_id)
    else:
        evidence_items = store.get_lot_evidence(lot_id)
    return LotEvidenceListResponse(items=[_build_lot_evidence_item(item) for item in evidence_items])


def create_lot_qc_review(lot_id: str, payload: CreateQCReviewRequest) -> QCReviewResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.qc_review", context=context)
    before_snapshot = copy.deepcopy(record)
    _assert_lot_access(
        context=context,
        action_name="lot.qc_review",
        lot_id=lot_id,
        allowed_roles=_LOT_QC_WRITE_ROLES,
        reason_code="forbidden_qc_review_write",
        detail="Actor is not allowed to create QC reviews.",
        before_snapshot=before_snapshot,
    )

    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return QCReviewResponse(**cached)

    if payload.result not in VALID_QC_RESULTS:
        _audit_lot(
            "lot.qc_review",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="unsupported_qc_result",
            metadata={"message": "Unsupported QC review result."},
        )
        raise HTTPException(status_code=422, detail="Unsupported QC review result.")

    actor_id = context["actor_id"]
    review_record = {
        "tenantId": record.get("tenantId", "default"),
        "checklistVersion": payload.checklistVersion,
        "result": payload.result,
        "reviewerId": actor_id,
        "notes": payload.notes,
    }

    if payload.result in {"pending", "needs_more_evidence", "passed"}:
        record["status"] = LotStatus.qc_pending.value
    elif payload.result == "failed":
        record["status"] = LotStatus.blocked.value

    if postgres_sync.is_enabled():
        with postgres_transaction():
            persisted = create_qc_review_with_lot_status(lot_id, record["status"], review_record, expected_version=record.get("version"))
            if persisted is None:
                raise HTTPException(status_code=500, detail="Failed to persist QC review.")
            event = _emit_lot_event(
                "lot.qc.reviewed",
                lot_id,
                payload={
                    "lotId": lot_id,
                    "result": payload.result,
                    "checklistVersion": payload.checklistVersion,
                    "status": record["status"],
                },
                context=context,
            )
            result = QCReviewResponse(data=_build_qc_review_item(persisted))
            _audit_lot(
                "lot.qc_review",
                lot_id,
                "allowed",
                context,
                before_snapshot=before_snapshot,
                after_snapshot=record,
                event=event,
                metadata={"qcReviewId": persisted["qcReviewId"]},
            )
            record_idempotency(
                key,
                result.model_dump(),
                operation_name="lot.qc_review",
                request_hash=build_request_hash(payload, extra={"action": "lot.qc_review", "lotId": lot_id}),
            )
    else:
        store.save_lot(lot_id, record)
        reviews = list(record.get("qcReviews", []))
        reviews.append(
            {
                "qcReviewId": str(uuid.uuid4()),
                "lotId": lot_id,
                "checklistVersion": payload.checklistVersion,
                "result": payload.result,
                "reviewerId": actor_id,
                "reviewedAt": store.now_iso(),
                "notes": payload.notes,
            }
        )
        store.save_lot_qc_reviews(lot_id, reviews)
        persisted = reviews[-1]
        event = _emit_lot_event(
            "lot.qc.reviewed",
            lot_id,
            payload={
                "lotId": lot_id,
                "result": payload.result,
                "checklistVersion": payload.checklistVersion,
                "status": record["status"],
            },
            context=context,
        )
        result = QCReviewResponse(data=_build_qc_review_item(persisted))
        _audit_lot(
            "lot.qc_review",
            lot_id,
            "allowed",
            context,
            before_snapshot=before_snapshot,
            after_snapshot=record,
            event=event,
            metadata={"qcReviewId": persisted["qcReviewId"]},
        )
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.qc_review",
            request_hash=build_request_hash(payload, extra={"action": "lot.qc_review", "lotId": lot_id}),
        )
    return result


def get_lot_qc_reviews(lot_id: str, meta: Meta | None = None) -> QCReviewListResponse:
    authorize_read_surface(
        meta=meta,
        action_name="lot.qc_review.list",
        target_type="Lot",
        target_id=lot_id,
        allowed_roles=_LOT_READ_ROLES,
        reason_code="forbidden_lot_read",
        detail="Actor is not allowed to read raw QC reviews.",
        allow_delegated_agent=False,
    )
    _get_lot_record_or_404(lot_id)
    if postgres_sync.is_enabled():
        reviews = list_qc_reviews(lot_id)
    else:
        reviews = store.get_lot_qc_reviews(lot_id)
    return QCReviewListResponse(items=[_build_qc_review_item(review) for review in reviews])
