from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models.enums import PreorderStatus
from app.store import memory


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


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
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert created.status_code == 201
    preorder = created.json()["data"]
    assert preorder["status"] == "draft"
    assert preorder["remainingQty"] == 12.0

    confirmed = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/confirm",
        json={"meta": {"correlationId": "corr-preorder-confirm", "idempotencyKey": "idem-preorder-confirm"}},
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"

    activated = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/activate",
        json={"meta": {"correlationId": "corr-preorder-activate", "idempotencyKey": "idem-preorder-activate"}},
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
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
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert adjusted.status_code == 200
    assert adjusted.json()["data"]["remainingQty"] == 10.0

    detail = client.get(
        f"/api/v1/preorders/{preorder['preorderId']}",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert detail.status_code == 200
    assert detail.json()["adjustmentHistory"][0]["oldCommittedQty"] == 12.0
    assert detail.json()["adjustmentHistory"][0]["newCommittedQty"] == 10.0

    cancelled = client.post(
        f"/api/v1/preorders/{preorder['preorderId']}/cancel",
        json={
            "reason": "customer no longer needs delivery",
            "meta": {"correlationId": "corr-preorder-cancel", "idempotencyKey": "idem-preorder-cancel"},
        },
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"
    assert cancelled.json()["data"]["cancelledQty"] == 10.0
    assert cancelled.json()["data"]["remainingQty"] == 0.0


def test_preorder_activate_route_rejects_completed_transition() -> None:
    memory.save_preorder(
        "preorder-api-completed",
        {
            "preorderId": "preorder-api-completed",
            "tenantId": "default",
            "preorderCode": "DT-API-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 5.0,
            "allocatedQty": 0.0,
            "deliveredQty": 5.0,
            "cancelledQty": 0.0,
            "remainingQty": 0.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.completed.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    response = client.post(
        "/api/v1/preorders/preorder-api-completed/activate",
        json={"meta": {"correlationId": "corr-preorder-api-completed", "idempotencyKey": "idem-preorder-api-completed"}},
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["message"] == "Preorder transition 'activate' not allowed from state 'completed'."


def test_preorder_route_rejects_viewer_create() -> None:
    customer = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Preorder Viewer User",
            "phone": "0900000401",
            "meta": {
                "correlationId": "corr-preorder-viewer-customer",
                "idempotencyKey": "idem-preorder-viewer-customer",
                "actorId": "sales-2",
                "actorRole": "sales",
            },
        },
    )
    customer_id = customer.json()["data"]["customerId"]

    response = client.post(
        "/api/v1/preorders",
        json={
            "customerId": customer_id,
            "productSkuId": "sku-1",
            "committedQty": 4,
            "meta": {"correlationId": "corr-preorder-viewer-deny", "idempotencyKey": "idem-preorder-viewer-deny"},
        },
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to create preorders."