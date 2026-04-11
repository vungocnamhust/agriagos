import copy
import uuid
from contextlib import nullcontext
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_lot_code
from app.core.write_context import append_audit_decision, build_request_hash, meta_context
from app.core.gateway import assert_lot_transition, check_idempotency, record_idempotency
from app.models.enums import LotStatus
from app.models.lots import (
    AddLotEvidenceRequest,
    BlockLotRequest,
    CreateHarvestedLotRequest,
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
)
from app.store.lots import (
    append_lot_evidence,
    create_lot_evidence,
    create_qc_review_with_lot_status,
    list_lot_evidence,
    list_qc_reviews,
)
from app.store import postgres_sync
from app.store import memory as store
from app.store._db import transaction as postgres_transaction


VALID_EVIDENCE_TYPES = {"photo", "video", "checklist", "note", "document", "measurement"}
VALID_QC_RESULTS = {"pending", "passed", "failed", "needs_more_evidence"}


def _new_lot_code(product_sku_id: str) -> str:
    # Use first 3 chars of the SKU id as the abbreviation; Phase 2 will use a proper SKU abbr field
    sku_abbr = product_sku_id[:3].upper()
    return generate_lot_code(sku_abbr)


def _build_lot_detail(record: dict[str, Any]) -> LotDetail:
    return LotDetail(
        lotId=record["lotId"],
        lotCode=record["lotCode"],
        productSkuId=record["productSkuId"],
        sourceType=record["sourceType"],
        sourceRefId=record["sourceRefId"],
        harvestOrProductionDate=record["harvestOrProductionDate"],
        actualQty=record["actualQty"],
        availableQty=record["availableQty"],
        reservedQty=record["reservedQty"],
        releasedQty=record["releasedQty"],
        status=record["status"],
    )


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
    append_audit_decision(
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
    key = context["idempotency_key"]
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    lot_id = str(uuid.uuid4())
    lot_code = _new_lot_code(payload.productSkuId)
    actor_id = context["actor_id"]

    record: dict[str, Any] = {
        "lotId": lot_id,
        "tenantId": "default",
        "lotCode": lot_code,
        "productSkuId": payload.productSkuId,
        "sourceType": payload.sourceType,
        "sourceRefId": payload.sourceRefId,
        "harvestOrProductionDate": payload.harvestOrProductionDate,
        "actualQty": payload.actualQty,
        "availableQty": 0.0,      # not available until released
        "reservedQty": 0.0,
        "releasedQty": 0.0,
        "qualityNote": payload.qualityNote,
        "attachments": list(payload.attachments),
        "status": LotStatus.harvested.value,
    }
    result = LotResponse(data=_build_lot_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            postgres_sync.upsert_lot(record)
            append_lot_evidence(lot_id, record["attachments"], actor_id)
        event = _emit_lot_event(
            "lot.harvest.created",
            lot_id,
            payload=record,
            context=context,
        )
        _audit_lot("lot.create", lot_id, "allowed", context, after_snapshot=record, event=event)
        record_idempotency(
            key,
            result.model_dump(),
            operation_name="lot.create",
            request_hash=build_request_hash(payload, extra={"action": "lot.create"}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, record)
    return result


def get_lot(lot_id: str) -> LotDetail:
    return _build_lot_detail(_get_lot_record_or_404(lot_id))


def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.release", context=context)
    before_snapshot = copy.deepcopy(record)

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

    if payload.releasedQty > record["actualQty"]:
        _audit_lot(
            "lot.release",
            lot_id,
            "denied",
            context,
            before_snapshot=before_snapshot,
            reason_code="released_qty_exceeds_actual",
            metadata={"message": f"releasedQty ({payload.releasedQty}) exceeds actualQty ({record['actualQty']})."},
        )
        raise HTTPException(
            status_code=422,
            detail=f"releasedQty ({payload.releasedQty}) exceeds actualQty ({record['actualQty']}).",
        )

    record["status"] = next_status
    record["releasedQty"] = payload.releasedQty
    record["availableQty"] = payload.releasedQty
    if payload.qualityStatus:
        record["qualityStatus"] = payload.qualityStatus
    result = LotResponse(data=_build_lot_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            postgres_sync.upsert_lot(record)
        event = _emit_lot_event(
            "lot.released",
            lot_id,
            payload={"lotId": lot_id, "releasedQty": payload.releasedQty, "status": next_status},
            context=context,
        )
        _audit_lot(
            "lot.release",
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
            operation_name="lot.release",
            request_hash=build_request_hash(payload, extra={"action": "lot.release", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, record)
    return result


def block_lot(lot_id: str, payload: BlockLotRequest) -> LotResponse:
    context = meta_context(payload.meta)
    record = _get_lot_record_or_404(lot_id, action_name="lot.block", context=context)
    before_snapshot = copy.deepcopy(record)

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
    record["status"] = next_status
    record["blockReason"] = payload.reason
    result = LotResponse(data=_build_lot_detail(record))
    with postgres_transaction() if postgres_sync.is_enabled() else nullcontext():
        if postgres_sync.is_enabled():
            postgres_sync.upsert_lot(record)
        event = _emit_lot_event(
            "lot.blocked",
            lot_id,
            payload={"lotId": lot_id, "reason": payload.reason, "status": next_status},
            context=context,
        )
        _audit_lot(
            "lot.block",
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
            operation_name="lot.block",
            request_hash=build_request_hash(payload, extra={"action": "lot.block", "lotId": lot_id}),
        )

    if not postgres_sync.is_enabled():
        store.save_lot(lot_id, record)
    return result


def add_lot_evidence(lot_id: str, payload: AddLotEvidenceRequest) -> LotEvidenceResponse:
    context = meta_context(payload.meta)
    lot = _get_lot_record_or_404(lot_id, action_name="lot.evidence_add", context=context)
    before_snapshot = copy.deepcopy(lot)

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


def get_lot_evidence(lot_id: str) -> LotEvidenceListResponse:
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
            persisted = create_qc_review_with_lot_status(lot_id, record["status"], review_record)
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


def get_lot_qc_reviews(lot_id: str) -> QCReviewListResponse:
    _get_lot_record_or_404(lot_id)
    if postgres_sync.is_enabled():
        reviews = list_qc_reviews(lot_id)
    else:
        reviews = store.get_lot_qc_reviews(lot_id)
    return QCReviewListResponse(items=[_build_qc_review_item(review) for review in reviews])
