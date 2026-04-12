from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def _auth_headers(role: str = "admin", actor_id: str | None = None) -> dict[str, str]:
    resolved_actor_id = actor_id or f"{role}-actor"
    return {
        "X-Actor-Id": resolved_actor_id,
        "X-Actor-Role": role,
    }


def _delegated_agent_headers(delegated_role: str, actor_id: str = "agent-actor") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": "agent",
        "X-Delegated-Actor-Role": delegated_role,
    }


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
        headers=_auth_headers(),
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

    detail_response = client.get(f"/api/v1/lots/{created['lotId']}", headers=_auth_headers())
    assert detail_response.status_code == 200
    assert detail_response.json()["lotId"] == created["lotId"]
    assert detail_response.json()["sourceRefId"] == "cycle-api-1"

    adjust_response = client.post(
        f"/api/v1/lots/{created['lotId']}/adjust",
        headers=_auth_headers(),
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
        headers=_auth_headers(),
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
        headers=_auth_headers(),
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
        headers=_auth_headers(),
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


def test_raw_lot_detail_route_denies_viewer() -> None:
    memory.save_lot(
        "lot-api-viewer-denied",
        {
            "lotId": "lot-api-viewer-denied",
            "tenantId": "default",
            "lotCode": "LOT-API-VIEWER-001",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-viewer-denied",
            "harvestOrProductionDate": "2026-04-11",
            "actualQty": 10.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
            "releasedQty": 0.0,
            "status": "harvested",
        },
    )

    response = client.get(
        "/api/v1/lots/lot-api-viewer-denied",
        headers=_auth_headers("viewer"),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Actor is not allowed to read raw lot details."


def test_raw_lot_detail_route_denies_delegated_agent() -> None:
    memory.save_lot(
        "lot-api-agent-denied",
        {
            "lotId": "lot-api-agent-denied",
            "tenantId": "default",
            "lotCode": "LOT-API-AGENT-001",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-agent-denied",
            "harvestOrProductionDate": "2026-04-11",
            "actualQty": 10.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
            "releasedQty": 0.0,
            "status": "harvested",
        },
    )

    response = client.get(
        "/api/v1/lots/lot-api-agent-denied",
        headers=_delegated_agent_headers("ops"),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Actor is not allowed to read raw lot details."


def test_qc_reviewer_can_read_evidence_and_qc_reviews() -> None:
    memory.save_lot(
        "lot-api-qc-read",
        {
            "lotId": "lot-api-qc-read",
            "tenantId": "default",
            "lotCode": "LOT-API-QC-001",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-qc-read",
            "harvestOrProductionDate": "2026-04-11",
            "actualQty": 10.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
            "releasedQty": 0.0,
            "status": "qc_pending",
        },
    )
    memory.save_lot_evidence(
        "lot-api-qc-read",
        [
            {
                "lotEvidenceId": "evidence-qc-read-1",
                "lotId": "lot-api-qc-read",
                "evidenceType": "photo",
                "objectStorageKey": "evidence/qc-read-1.jpg",
                "textValue": None,
                "capturedAt": "2026-04-11T10:00:00Z",
                "actorId": "qc-1",
                "status": "active",
            }
        ],
    )
    memory.save_lot_qc_reviews(
        "lot-api-qc-read",
        [
            {
                "qcReviewId": "review-qc-read-1",
                "lotId": "lot-api-qc-read",
                "checklistVersion": "v1",
                "result": "passed",
                "reviewerId": "qc-1",
                "reviewedAt": "2026-04-11T11:00:00Z",
                "notes": None,
            }
        ],
    )

    evidence_response = client.get(
        "/api/v1/lots/lot-api-qc-read/evidence",
        headers=_auth_headers("qc_reviewer", actor_id="qc-1"),
    )
    reviews_response = client.get(
        "/api/v1/lots/lot-api-qc-read/qc-reviews",
        headers=_auth_headers("qc_reviewer", actor_id="qc-1"),
    )

    assert evidence_response.status_code == 200
    assert evidence_response.json()["items"][0]["evidenceType"] == "photo"
    assert reviews_response.status_code == 200
    assert reviews_response.json()["items"][0]["result"] == "passed"


def test_lot_release_block_and_unblock_workflow() -> None:
    memory.save_crop_cycle(
        "cycle-api-unblock",
        {
            "cropCycleId": "cycle-api-unblock",
            "plotId": "plot-1",
            "cropName": "rice",
            "growthStage": "harvested",
            "status": "harvested",
        },
    )

    create_response = client.post(
        "/api/v1/lots",
        headers=_auth_headers(),
        json={
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-api-unblock",
            "actualQty": 25,
            "harvestOrProductionDate": "2026-04-11",
            "requiresQc": True,
            "meta": {"correlationId": "corr-lot-api-unblock-create", "idempotencyKey": "idem-lot-api-unblock-create"},
        },
    )

    assert create_response.status_code == 201
    lot_id = create_response.json()["data"]["lotId"]

    block_response = client.post(
        f"/api/v1/lots/{lot_id}/block",
        headers=_auth_headers(),
        json={
            "reason": "awaiting evidence",
            "meta": {"correlationId": "corr-lot-api-unblock-block", "idempotencyKey": "idem-lot-api-unblock-block"},
        },
    )

    assert block_response.status_code == 200
    assert block_response.json()["data"]["status"] == "blocked"

    unblock_response = client.post(
        f"/api/v1/lots/{lot_id}/unblock",
        headers=_auth_headers(),
        json={
            "reason": "evidence uploaded",
            "meta": {"correlationId": "corr-lot-api-unblock", "idempotencyKey": "idem-lot-api-unblock"},
        },
    )

    assert unblock_response.status_code == 200
    data = unblock_response.json()["data"]
    assert data["status"] == "qc_pending"
    assert data["availableQty"] == 0
    assert data["releasedQty"] == 0


def test_sensitive_lot_release_requires_approval_ref() -> None:
    memory.save_crop_cycle(
        "cycle-api-sensitive-release",
        {
            "cropCycleId": "cycle-api-sensitive-release",
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
            "sourceRefId": "cycle-api-sensitive-release",
            "actualQty": 25,
            "harvestOrProductionDate": "2026-04-11",
            "meta": {
                "correlationId": "corr-lot-api-sensitive-release-create",
                "idempotencyKey": "idem-lot-api-sensitive-release-create",
                "actorId": "farm-manager-1",
                "actorRole": "farm_manager",
            },
        },
    )

    assert create_response.status_code == 201
    lot_id = create_response.json()["data"]["lotId"]

    denied_response = client.post(
        f"/api/v1/lots/{lot_id}/release",
        json={
            "releasedQty": 10,
            "meta": {
                "correlationId": "corr-lot-api-sensitive-release-denied",
                "idempotencyKey": "idem-lot-api-sensitive-release-denied",
                "actorId": "farm-manager-1",
                "actorRole": "farm_manager",
            },
        },
    )

    assert denied_response.status_code == 403
    assert denied_response.json()["message"] == "Sensitive lot release requires approvalRef."

    allowed_response = client.post(
        f"/api/v1/lots/{lot_id}/release",
        json={
            "releasedQty": 10,
            "approvalRef": "APR-LOT-002",
            "meta": {
                "correlationId": "corr-lot-api-sensitive-release-allowed",
                "idempotencyKey": "idem-lot-api-sensitive-release-allowed",
                "actorId": "farm-manager-1",
                "actorRole": "farm_manager",
            },
        },
    )

    assert allowed_response.status_code == 200
    assert allowed_response.json()["data"]["status"] == "released"


def test_harvested_lot_route_rejects_processing_batch_source() -> None:
    response = client.post(
        "/api/v1/lots",
        headers=_auth_headers(),
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


def test_lot_release_route_rejects_blocked_transition() -> None:
    memory.save_lot(
        "lot-api-blocked",
        {
            "lotId": "lot-api-blocked",
            "tenantId": "default",
            "lotCode": "LOT-API-BLOCKED-001",
            "productSkuId": "sku-1",
            "sourceType": "crop_cycle",
            "sourceRefId": "cycle-api-blocked",
            "harvestOrProductionDate": "2026-04-11",
            "actualQty": 10.0,
            "availableQty": 0.0,
            "reservedQty": 0.0,
            "releasedQty": 0.0,
            "status": "blocked",
        },
    )

    response = client.post(
        "/api/v1/lots/lot-api-blocked/release",
        headers=_auth_headers(),
        json={
            "releasedQty": 5,
            "meta": {"correlationId": "corr-lot-api-blocked-release", "idempotencyKey": "idem-lot-api-blocked-release"},
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["message"] == "Lot transition 'release' not allowed from state 'blocked'."