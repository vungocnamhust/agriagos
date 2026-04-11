from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.common import Meta
from app.models.lots import AdjustLotQuantityRequest, CreateHarvestedLotRequest, CreateProcessedLotRequest, ReleaseLotRequest
from app.services import lots
from app.store import memory


def test_create_lot_records_event_audit_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-1",
        {
            "cropCycleId": "cycle-1",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )

    response = lots.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="crop_cycle",
            sourceRefId="cycle-1",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot", idempotencyKey="idem-lot"),
        )
    )

    assert memory.get_lot(response.data.lotId) is not None
    assert memory.list_events()[-1]["eventName"] == "lot.harvest.created"
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.create"
    assert memory.get_idempotent_result("idem-lot")["data"]["lotId"] == response.data.lotId


def test_create_processed_lot_records_processed_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    response = lots.create_processed_lot(
        CreateProcessedLotRequest(
            productSkuId="sku-1",
            processRefId="batch-1",
            actualQty=18,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot-process", idempotencyKey="idem-lot-process"),
        )
    )

    assert response.data.sourceType == "processing_batch"
    assert memory.list_events()[-1]["eventName"] == "lot.processed.created"


def test_create_harvested_lot_request_rejects_processing_batch_source() -> None:
    with pytest.raises(ValidationError):
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="processing_batch",
            sourceRefId="batch-1",
            actualQty=18,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot-process-invalid", idempotencyKey="idem-lot-process-invalid"),
        )


def test_release_lot_missing_aggregate_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            "missing-lot",
            ReleaseLotRequest(releasedQty=5, meta=Meta(correlationId="corr-release")),
        )

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.release"
    assert memory.list_audit_logs()[-1]["targetId"] == "missing-lot"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "lot_not_found"


def test_create_lot_rejects_non_positive_quantity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        lots.create_harvested_lot(
            CreateHarvestedLotRequest(
                productSkuId="sku-1",
                sourceType="crop_cycle",
                sourceRefId="cycle-1",
                actualQty=0,
                harvestOrProductionDate="2026-04-11",
                meta=Meta(correlationId="corr-lot-invalid-qty", idempotencyKey="idem-lot-invalid-qty"),
            )
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "invalid_quantity"


def test_create_lot_validates_crop_cycle_source_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        lots.create_harvested_lot(
            CreateHarvestedLotRequest(
                productSkuId="sku-1",
                sourceType="crop_cycle",
                sourceRefId="missing-cycle",
                actualQty=25,
                harvestOrProductionDate="2026-04-11",
                meta=Meta(correlationId="corr-lot-missing-cycle", idempotencyKey="idem-lot-missing-cycle"),
            )
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "source_ref_not_found"


def test_create_lot_initializes_qc_pending_when_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-1",
        {
            "cropCycleId": "cycle-1",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )

    response = lots.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="crop_cycle",
            sourceRefId="cycle-1",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            requiresQc=True,
            meta=Meta(correlationId="corr-lot-qc", idempotencyKey="idem-lot-qc"),
        )
    )

    assert response.data.status == "qc_pending"


def test_adjust_lot_quantity_emits_event_and_updates_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-3",
        {
            "cropCycleId": "cycle-3",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )
    created = lots.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="crop_cycle",
            sourceRefId="cycle-3",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot-adjust-create", idempotencyKey="idem-lot-adjust-create"),
        )
    )

    adjusted = lots.adjust_lot_quantity(
        created.data.lotId,
        AdjustLotQuantityRequest(
            newActualQty=30,
            reason="reweighed after intake",
            meta=Meta(correlationId="corr-lot-adjust", idempotencyKey="idem-lot-adjust", actorId="ops-1"),
        ),
    )

    assert adjusted.data.actualQty == 30
    assert memory.list_events()[-1]["eventName"] == "lot.adjusted"
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.adjust_quantity"


def test_adjust_lot_quantity_rejects_qty_below_released(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-4",
        {
            "cropCycleId": "cycle-4",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )
    created = lots.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="crop_cycle",
            sourceRefId="cycle-4",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot-adjust-limit-create", idempotencyKey="idem-lot-adjust-limit-create"),
        )
    )
    lots.release_lot(
        created.data.lotId,
        ReleaseLotRequest(
            releasedQty=10,
            meta=Meta(correlationId="corr-lot-adjust-limit-release", idempotencyKey="idem-lot-adjust-limit-release"),
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        lots.adjust_lot_quantity(
            created.data.lotId,
            AdjustLotQuantityRequest(
                newActualQty=5,
                reason="bad recount",
                meta=Meta(correlationId="corr-lot-adjust-limit", idempotencyKey="idem-lot-adjust-limit", actorId="ops-1"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "adjusted_qty_below_released_qty"
