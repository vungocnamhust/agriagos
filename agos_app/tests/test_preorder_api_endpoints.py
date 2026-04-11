from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_preorder_routes_support_draft_lifecycle_adjust_and_cancel() -> None:
    customer = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Preorder API User",
            "phone": "0900000400",
            "meta": {
                "correlationId": "corr-preorder-customer",
                "idempotencyKey": "idem-preorder-customer",
                "actorId": "sales-1",
                "actorRole": "sales",
            },
        },
    )
    assert customer.status_code == 201
    customer_id = customer.json()["data"]["customerId"]

    created = client.post(
        "/api/v1/preorders",
        json={
            "customerId": customer_id,
            "productSkuId": "sku-1",
            "committedQty": 12,
            "meta": {
                "correlationId": "corr-preorder-create",
                "idempotencyKey": "idem-preorder-create",
            },
        },
    )
    assert created.status_code == 201
    preorder = created.json()["data"]
    assert preorder["status"] == "draft"
    assert preorder["remainingQty"] == 12.0

    confirmed = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/confirm",
        json={"meta": {"correlationId": "corr-preorder-confirm", "idempotencyKey": "idem-preorder-confirm"}},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"

    activated = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/activate",
        json={"meta": {"correlationId": "corr-preorder-activate", "idempotencyKey": "idem-preorder-activate"}},
    )
    assert activated.status_code == 200
    assert activated.json()["data"]["status"] == "active"

    adjusted = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/adjust",
        json={
            "newCommittedQty": 10,
            "reason": "customer reduced quota",
            "meta": {"correlationId": "corr-preorder-adjust", "idempotencyKey": "idem-preorder-adjust"},
        },
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["remainingQty"] == 10.0

    detail = client.get(f"/api/v1/preorders/{preorder['preorderId']}")
    assert detail.status_code == 200
    assert detail.json()["adjustmentHistory"][0]["oldCommittedQty"] == 12.0
    assert detail.json()["adjustmentHistory"][0]["newCommittedQty"] == 10.0

    cancelled = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/cancel",
        json={
            "reason": "customer no longer needs delivery",
            "meta": {"correlationId": "corr-preorder-cancel", "idempotencyKey": "idem-preorder-cancel"},
        },
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["cancelledQty"] == 10.0
    assert cancelled.json()["data"]["remainingQty"] == 0.0