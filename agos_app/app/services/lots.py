import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.codegen import generate_lot_code
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


def _get_lot_record_or_404(lot_id: str) -> dict[str, Any]:
    if postgres_sync.is_enabled():
        record = postgres_sync.fetch_lot(lot_id)
    else:
        record = store.get_lot(lot_id)

    if not record:
        raise HTTPException(status_code=404, detail="Lot not found.")
    return record


def create_harvested_lot(payload: CreateHarvestedLotRequest) -> LotResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    lot_id = str(uuid.uuid4())
    lot_code = _new_lot_code(payload.productSkuId)
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

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
    if postgres_sync.is_enabled():
        postgres_sync.upsert_lot(record)
        append_lot_evidence(lot_id, record["attachments"], actor_id)
    else:
        store.save_lot(lot_id, record)

    events.emit(
        "lot.harvest.created",
        "Lot",
        lot_id,
        payload=record,
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = LotResponse(data=_build_lot_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def get_lot(lot_id: str) -> LotDetail:
    return _build_lot_detail(_get_lot_record_or_404(lot_id))


def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    record = _get_lot_record_or_404(lot_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    next_status = assert_lot_transition(record, "release")

    if payload.releasedQty > record["actualQty"]:
        raise HTTPException(
            status_code=422,
            detail=f"releasedQty ({payload.releasedQty}) exceeds actualQty ({record['actualQty']}).",
        )

    record["status"] = next_status
    record["releasedQty"] = payload.releasedQty
    record["availableQty"] = payload.releasedQty
    if payload.qualityStatus:
        record["qualityStatus"] = payload.qualityStatus
    if postgres_sync.is_enabled():
        postgres_sync.upsert_lot(record)
    else:
        store.save_lot(lot_id, record)

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    events.emit(
        "lot.released",
        "Lot",
        lot_id,
        payload={"lotId": lot_id, "releasedQty": payload.releasedQty, "status": next_status},
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = LotResponse(data=_build_lot_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def block_lot(lot_id: str, payload: BlockLotRequest) -> LotResponse:
    record = _get_lot_record_or_404(lot_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    next_status = assert_lot_transition(record, "block")
    record["status"] = next_status
    record["blockReason"] = payload.reason
    if postgres_sync.is_enabled():
        postgres_sync.upsert_lot(record)
    else:
        store.save_lot(lot_id, record)

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    events.emit(
        "lot.blocked",
        "Lot",
        lot_id,
        payload={"lotId": lot_id, "reason": payload.reason, "status": next_status},
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = LotResponse(data=_build_lot_detail(record))
    record_idempotency(key, result.model_dump())
    return result


def add_lot_evidence(lot_id: str, payload: AddLotEvidenceRequest) -> LotEvidenceResponse:
    lot = _get_lot_record_or_404(lot_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotEvidenceResponse(**cached)

    if payload.evidenceType not in VALID_EVIDENCE_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported evidenceType.")
    if not payload.objectStorageKey and not payload.textValue:
        raise HTTPException(status_code=422, detail="Evidence requires objectStorageKey or textValue.")

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    evidence_record = {
        "tenantId": lot.get("tenantId", "default"),
        "evidenceType": payload.evidenceType,
        "objectStorageKey": payload.objectStorageKey,
        "textValue": payload.textValue,
        "actorId": actor_id,
        "status": "active",
    }

    if postgres_sync.is_enabled():
        persisted = create_lot_evidence(lot_id, evidence_record)
        if persisted is None:
            raise HTTPException(status_code=500, detail="Failed to persist lot evidence.")
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

    events.emit(
        "lot.evidence.added",
        "Lot",
        lot_id,
        payload={
            "lotId": lot_id,
            "evidenceType": payload.evidenceType,
            "objectStorageKey": payload.objectStorageKey,
            "hasTextValue": bool(payload.textValue),
        },
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = LotEvidenceResponse(data=_build_lot_evidence_item(persisted))
    record_idempotency(key, result.model_dump())
    return result


def get_lot_evidence(lot_id: str) -> LotEvidenceListResponse:
    _get_lot_record_or_404(lot_id)
    if postgres_sync.is_enabled():
        evidence_items = list_lot_evidence(lot_id)
    else:
        evidence_items = store.get_lot_evidence(lot_id)
    return LotEvidenceListResponse(items=[_build_lot_evidence_item(item) for item in evidence_items])


def create_lot_qc_review(lot_id: str, payload: CreateQCReviewRequest) -> QCReviewResponse:
    record = _get_lot_record_or_404(lot_id)

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return QCReviewResponse(**cached)

    if payload.result not in VALID_QC_RESULTS:
        raise HTTPException(status_code=422, detail="Unsupported QC review result.")

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
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

    if not postgres_sync.is_enabled():
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
    else:
        persisted = create_qc_review_with_lot_status(lot_id, record["status"], review_record)
        if persisted is None:
            raise HTTPException(status_code=500, detail="Failed to persist QC review.")

    events.emit(
        "lot.qc.reviewed",
        "Lot",
        lot_id,
        payload={
            "lotId": lot_id,
            "result": payload.result,
            "checklistVersion": payload.checklistVersion,
            "status": record["status"],
        },
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = QCReviewResponse(data=_build_qc_review_item(persisted))
    record_idempotency(key, result.model_dump())
    return result


def get_lot_qc_reviews(lot_id: str) -> QCReviewListResponse:
    _get_lot_record_or_404(lot_id)
    if postgres_sync.is_enabled():
        reviews = list_qc_reviews(lot_id)
    else:
        reviews = store.get_lot_qc_reviews(lot_id)
    return QCReviewListResponse(items=[_build_qc_review_item(review) for review in reviews])
