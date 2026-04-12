from __future__ import annotations

from contextlib import nullcontext

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.models.common import Meta
from app.models.lots import (
    AdjustLotQuantityRequest,
    BlockLotRequest,
    CreateHarvestedLotRequest,
    CreateProcessedLotRequest,
    CreateQCReviewRequest,
    ReleaseLotRequest,
    UnblockLotRequest,
)
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


def test_create_processed_lot_rejects_blank_process_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        lots.create_processed_lot(
            CreateProcessedLotRequest(
                productSkuId="sku-1",
                processRefId="   ",
                actualQty=18,
                harvestOrProductionDate="2026-04-11",
                meta=Meta(correlationId="corr-lot-process-blank", idempotencyKey="idem-lot-process-blank"),
            )
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "processRefId is required."
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.processed_create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "invalid_source_ref"


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
            approvalRef="APR-LOT-ADJUST-001",
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


def test_unblock_lot_moves_blocked_status_back_to_qc_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_lot(
        "lot-blocked-1",
        {
            "lotId": "lot-blocked-1",
            "tenantId": "default",
            "lotCode": "LOT-BLOCKED-001",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-1",
            "harvestOrProductionDate": "2026-04-11",
            "status": "blocked",
            "actualQty": 10.0,
            "releasedQty": 0.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
        },
    )

    response = lots.unblock_lot(
        "lot-blocked-1",
        UnblockLotRequest(
            reason="needs_reinspection",
            meta=Meta(correlationId="corr-lot-unblock"),
        ),
    )

    assert response.data.status == "qc_pending"
    assert memory.list_events()[-1]["eventName"] == "lot.unblocked"


def test_release_lot_rejects_blocked_to_released_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_lot(
        "lot-blocked-2",
        {
            "lotId": "lot-blocked-2",
            "tenantId": "default",
            "lotCode": "LOT-BLOCKED-002",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-2",
            "harvestOrProductionDate": "2026-04-11",
            "status": "blocked",
            "actualQty": 10.0,
            "releasedQty": 0.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            "lot-blocked-2",
            ReleaseLotRequest(releasedQty=5, meta=Meta(correlationId="corr-lot-blocked-release")),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Lot transition 'release' not allowed from state 'blocked'."
    assert memory.list_audit_logs()[-1]["reasonCode"] == "state_transition_rejected"


def test_block_lot_closes_available_inventory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-block-release",
        {
            "cropCycleId": "cycle-block-release",
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
            sourceRefId="cycle-block-release",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot-block-release-create", idempotencyKey="idem-lot-block-release-create"),
        )
    )
    lots.release_lot(
        created.data.lotId,
        ReleaseLotRequest(
            releasedQty=10,
            approvalRef="APR-LOT-BLOCK-001",
            meta=Meta(correlationId="corr-lot-block-release-release", idempotencyKey="idem-lot-block-release-release"),
        ),
    )

    blocked = lots.block_lot(
        created.data.lotId,
        BlockLotRequest(
            reason="qc failed",
            meta=Meta(correlationId="corr-lot-block-release-block", idempotencyKey="idem-lot-block-release-block"),
        ),
    )

    assert blocked.data.status == "blocked"
    assert blocked.data.availableQty == 0
    assert blocked.data.releasedQty == 0
    assert memory.list_events()[-1]["eventName"] == "lot.blocked"


def test_release_lot_from_qc_pending_requires_passed_review(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-release-guard",
        {
            "cropCycleId": "cycle-release-guard",
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
            sourceRefId="cycle-release-guard",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            requiresQc=True,
            meta=Meta(correlationId="corr-lot-release-guard-create", idempotencyKey="idem-lot-release-guard-create"),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            created.data.lotId,
            ReleaseLotRequest(
                releasedQty=10,
                meta=Meta(correlationId="corr-lot-release-guard", idempotencyKey="idem-lot-release-guard"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Lot requires a passed QC review before release."

    qc_review = lots.create_lot_qc_review(
        created.data.lotId,
        CreateQCReviewRequest(
            checklistVersion="v1",
            result="passed",
            meta=Meta(correlationId="corr-lot-release-guard-review", idempotencyKey="idem-lot-release-guard-review"),
        ),
    )

    assert qc_review.data.result == "passed"

    released = lots.release_lot(
        created.data.lotId,
        ReleaseLotRequest(
            releasedQty=10,
            meta=Meta(correlationId="corr-lot-release-guard-allowed", idempotencyKey="idem-lot-release-guard-allowed"),
        ),
    )

    assert released.data.status == "released"
    assert released.data.availableQty == 10


def test_release_lot_from_harvested_requires_approval_for_sensitive_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-sensitive-release",
        {
            "cropCycleId": "cycle-sensitive-release",
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
            sourceRefId="cycle-sensitive-release",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(
                correlationId="corr-lot-sensitive-release-create",
                idempotencyKey="idem-lot-sensitive-release-create",
                actorId="farm-manager-1",
                actorRole="farm_manager",
            ),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            created.data.lotId,
            ReleaseLotRequest(
                releasedQty=10,
                meta=Meta(
                    correlationId="corr-lot-sensitive-release-denied",
                    idempotencyKey="idem-lot-sensitive-release-denied",
                    actorId="farm-manager-1",
                    actorRole="farm_manager",
                ),
            ),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Sensitive lot release requires approvalRef."
    escalated_audit = memory.list_audit_logs()[-1]
    assert escalated_audit["decision"] == "escalated"
    assert escalated_audit["reasonCode"] == "approval_required"
    assert escalated_audit["afterSnapshot"] is None
    assert escalated_audit["beforeSnapshot"]["status"] == "harvested"
    assert escalated_audit["metadata"]["requiredApprovalRef"] is True

    released = lots.release_lot(
        created.data.lotId,
        ReleaseLotRequest(
            releasedQty=10,
            approvalRef="APR-LOT-001",
            meta=Meta(
                correlationId="corr-lot-sensitive-release-allowed",
                idempotencyKey="idem-lot-sensitive-release-allowed",
                actorId="farm-manager-1",
                actorRole="farm_manager",
            ),
        ),
    )

    assert released.data.status == "released"
    assert memory.list_events()[-1]["payload"]["approvalRef"] == "APR-LOT-001"


def test_release_lot_persistence_failure_writes_failed_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(lots, "postgres_transaction", nullcontext)

    record = {
        "lotId": "lot-persist-fail",
        "tenantId": "default",
        "lotCode": "LOT-PERSIST-FAIL",
        "productSkuId": "sku-1",
        "sourceType": "crop_cycle",
        "sourceRefId": "cycle-1",
        "harvestOrProductionDate": "2026-04-11",
        "actualQty": 10.0,
        "availableQty": 0.0,
        "reservedQty": 0.0,
        "releasedQty": 0.0,
        "status": "harvested",
        "unit": "kg",
    }
    monkeypatch.setattr(lots.postgres_sync, "fetch_lot", lambda lot_id: dict(record))
    monkeypatch.setattr(
        lots.postgres_sync,
        "release_lot_atomic",
        lambda lot_id, next_status, released_qty, expected_version=None: None,
    )

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            "lot-persist-fail",
            ReleaseLotRequest(
                releasedQty=5,
                approvalRef="APR-PERSIST-FAIL",
                meta=Meta(correlationId="corr-lot-persist-fail", actorId="admin-1", actorRole="admin"),
            ),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == "Failed to persist lot release."
    failed_audit = memory.list_audit_logs()[-1]
    assert failed_audit["decision"] == "failed"
    assert failed_audit["reasonCode"] == "persistence_failed"
    assert failed_audit["beforeSnapshot"]["status"] == "harvested"
    assert failed_audit["afterSnapshot"] is None


def test_unblock_lot_returns_to_qc_pending_and_keeps_inventory_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)
    memory.save_crop_cycle(
        "cycle-unblock",
        {
            "cropCycleId": "cycle-unblock",
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
            sourceRefId="cycle-unblock",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            requiresQc=True,
            meta=Meta(correlationId="corr-lot-unblock-create", idempotencyKey="idem-lot-unblock-create"),
        )
    )
    lots.block_lot(
        created.data.lotId,
        BlockLotRequest(
            reason="missing evidence",
            meta=Meta(correlationId="corr-lot-unblock-block", idempotencyKey="idem-lot-unblock-block"),
        ),
    )

    unblocked = lots.unblock_lot(
        created.data.lotId,
        UnblockLotRequest(
            reason="evidence supplied",
            meta=Meta(correlationId="corr-lot-unblock", idempotencyKey="idem-lot-unblock"),
        ),
    )

    assert unblocked.data.status == "qc_pending"
    assert unblocked.data.availableQty == 0
    assert unblocked.data.releasedQty == 0
    assert memory.list_events()[-1]["eventName"] == "lot.unblocked"

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            created.data.lotId,
            ReleaseLotRequest(
                releasedQty=10,
                meta=Meta(correlationId="corr-lot-unblock-release-denied", idempotencyKey="idem-lot-unblock-release-denied"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Lot requires a passed QC review before release."
