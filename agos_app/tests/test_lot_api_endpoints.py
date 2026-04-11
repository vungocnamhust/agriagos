from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def test_lot_routes_create_detail_and_adjust() -> None:
    memory.save_crop_cycle(
        "cycle-api-1",
        {
            "cropCycleId": "cycle-api-1",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )

    create_response = client.post(
        "/api/v1/lots",
        json={
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-api-1",
            "actualQty": 25,
            "unit": "KG",
            "harvestOrProductionDate": "2026-04-11",
            "requiresQc": True,
            "meta": {"correlationId": "corr-lot-api-create", "idempotencyKey": "idem-lot-api-create"},
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()["data"]
    assert created["status"] == "qc_pending"
    assert created["unit"] == "kg"
    assert created["releasedQty"] == 0
    assert created["availableQty"] == 0

    detail_response = client.get(f"/api/v1/lots/{created['lotId']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["lotId"] == created["lotId"]
    assert detail_response.json()["sourceRefId"] == "cycle-api-1"

    adjust_response = client.post(
        f"/api/v1/lots/{created['lotId']}/adjust",
        json={
            "newActualQty": 30,
            "reason": "reweighed after intake",
            "meta": {"correlationId": "corr-lot-api-adjust", "idempotencyKey": "idem-lot-api-adjust", "actorId": "ops-1"},
        },
    )
    assert adjust_response.status_code == 200
    assert adjust_response.json()["data"]["actualQty"] == 30
    assert memory.list_events()[-1]["eventName"] == "lot.adjusted"


def test_lot_create_route_rejects_invalid_quantity_and_missing_cycle() -> None:
    invalid_quantity_response = client.post(
        "/api/v1/lots",
        json={
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-missing-for-invalid-qty-check",
            "actualQty": 0,
            "harvestOrProductionDate": "2026-04-11",
            "meta": {"correlationId": "corr-lot-api-invalid-qty", "idempotencyKey": "idem-lot-api-invalid-qty"},
        },
    )

    assert invalid_quantity_response.status_code == 422
    assert invalid_quantity_response.json()["message"] == "actualQty must be greater than 0."

    missing_cycle_response = client.post(
        "/api/v1/lots",
        json={
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "missing-cycle",
            "actualQty": 12,
            "harvestOrProductionDate": "2026-04-11",
            "meta": {"correlationId": "corr-lot-api-missing-cycle", "idempotencyKey": "idem-lot-api-missing-cycle"},
        },
    )

    assert missing_cycle_response.status_code == 422
    assert missing_cycle_response.json()["message"] == "Referenced crop cycle was not found."


def test_processed_lot_route_accepts_processing_batch_source() -> None:
    response = client.post(
        "/api/v1/lots/processed",
        json={
            "productSkuId": "sku-1",
            "processRefId": "batch-api-1",
            "actualQty": 14,
            "harvestOrProductionDate": "2026-04-11",
            "meta": {"correlationId": "corr-lot-api-process", "idempotencyKey": "idem-lot-api-process"},
        },
    )

    assert response.status_code == 201
    assert response.json()["data"]["sourceType"] == "processing_batch"


def test_harvested_lot_route_rejects_processing_batch_source() -> None:
    response = client.post(
        "/api/v1/lots",
        json={
            "productSkuId": "sku-1",
            "sourceType": "processing_batch",
            "sourceRefId": "batch-api-1",
            "actualQty": 14,
            "harvestOrProductionDate": "2026-04-11",
            "meta": {"correlationId": "corr-lot-api-harvested-invalid", "idempotencyKey": "idem-lot-api-harvested-invalid"},
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Request validation failed"