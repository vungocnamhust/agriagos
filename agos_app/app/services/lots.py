import uuid
from typing import Any

from fastapi import HTTPException

from app.core import events
from app.core.gateway import assert_lot_transition, check_idempotency, record_idempotency
from app.models.enums import LotStatus
from app.models.lots import (
    BlockLotRequest,
    CreateHarvestedLotRequest,
    LotDetail,
    LotResponse,
    ReleaseLotRequest,
)
from app.store import memory as store


def _new_lot_code() -> str:
    return f"LOT-{str(uuid.uuid4())[:8].upper()}"


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


def create_harvested_lot(payload: CreateHarvestedLotRequest) -> LotResponse:
    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    lot_id = str(uuid.uuid4())
    lot_code = _new_lot_code()
    correlation_id = payload.meta.correlationId if payload.meta else None
    actor_id = payload.meta.actorId if payload.meta else None

    record: dict[str, Any] = {
        "lotId": lot_id,
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
    store._lots[lot_id] = record

    events.emit(
        "HarvestedLotCreated",
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
    record = store._lots.get(lot_id)
    if not record:
        raise HTTPException(status_code=404, detail="Lot not found.")
    return _build_lot_detail(record)


def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    record = store._lots.get(lot_id)
    if not record:
        raise HTTPException(status_code=404, detail="Lot not found.")

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

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    events.emit(
        "LotReleased",
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
    record = store._lots.get(lot_id)
    if not record:
        raise HTTPException(status_code=404, detail="Lot not found.")

    key = payload.meta.idempotencyKey if payload.meta else None
    if cached := check_idempotency(key):
        return LotResponse(**cached)

    next_status = assert_lot_transition(record, "block")
    record["status"] = next_status
    record["blockReason"] = payload.reason

    actor_id = payload.meta.actorId if payload.meta else None
    correlation_id = payload.meta.correlationId if payload.meta else None
    events.emit(
        "LotBlocked",
        "Lot",
        lot_id,
        payload={"lotId": lot_id, "reason": payload.reason, "status": next_status},
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    result = LotResponse(data=_build_lot_detail(record))
    record_idempotency(key, result.model_dump())
    return result
