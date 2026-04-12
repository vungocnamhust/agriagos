from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory
from app.models.enums import LotStatus


client = TestClient(app)


def _create_customer() -> str:
    response = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Order API User",
            "phone": "0900000500",
            "meta": {
                "correlationId": "corr-order-customer",
                "idempotencyKey": "idem-order-customer",
                "actorId": "sales-1",
                "actorRole": "sales",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["customerId"]


def _create_preorder(customer_id: str) -> str:
    created = client.post(
        "/api/v1/preorders",
        json={
            "customerId": customer_id,
            "productSkuId": "sku-1",
            "committedQty": 12,
            "meta": {
                "correlationId": "corr-api-preorder-create",
                "idempotencyKey": "idem-api-preorder-create",
            },
        },
    )
    assert created.status_code == 201
    preorder_id = created.json()["data"]["preorderId"]

    confirmed = client.post(
        f"/api/v1/preorders/{preorder_id}/confirm",
        json={"meta": {"correlationId": "corr-api-preorder-confirm", "idempotencyKey": "idem-api-preorder-confirm"}},
    )
    assert confirmed.status_code == 200

    activated = client.post(
        f"/api/v1/preorders/{preorder_id}/activate",
        json={"meta": {"correlationId": "corr-api-preorder-activate", "idempotencyKey": "idem-api-preorder-activate"}},
    )
    assert activated.status_code == 200
    return preorder_id


def _seed_released_lot(*, lot_id: str, available_qty: float) -> None:
    memory.save_lot(
        lot_id,
        {
            "lotId": lot_id,
            "status": LotStatus.released.value,
            "availableQty": available_qty,
            "reservedQty": 0.0,
            "releasedQty": available_qty,
        },
    )


def test_order_routes_create_get_and_confirm_preserve_line_level_linkage() -> None:
    customer_id = _create_customer()
    preorder_id = _create_preorder(customer_id)

    created = client.post(
        "/api/v1/orders",
        json={
            "customerId": customer_id,
            "channel": "direct",
            "lines": [
                {
                    "productSkuId": "sku-1",
                    "orderedQty": 5,
                    "unit": "kg",
                    "sourcePreorderId": preorder_id,
                },
                {
                    "productSkuId": "sku-2",
                    "orderedQty": 2,
                    "unit": "kg",
                },
            ],
            "meta": {
                "correlationId": "corr-api-order-create",
                "idempotencyKey": "idem-api-order-create",
            },
        },
    )
    assert created.status_code == 201
    created_body = created.json()["data"]
    assert created_body["status"] == "draft"
    assert created_body["sourcePreorderFlag"] is True
    assert created_body["lines"][0]["sourcePreorderId"] == preorder_id
    assert created_body["lines"][1]["sourcePreorderId"] is None

    detail = client.get(f"/api/v1/orders/{created_body['orderId']}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["sourcePreorderFlag"] is True
    assert detail_body["lines"][0]["sourcePreorderId"] == preorder_id
    assert detail_body["lines"][1]["sourcePreorderId"] is None

    confirmed = client.post(
        f"/api/v1/orders/{created_body['orderId']}/confirm",
        json={"meta": {"correlationId": "corr-api-order-confirm", "idempotencyKey": "idem-api-order-confirm"}},
    )
    assert confirmed.status_code == 200
    confirmed_body = confirmed.json()["data"]
    assert confirmed_body["status"] == "confirmed"
    assert confirmed_body["sourcePreorderFlag"] is True
    assert confirmed_body["lines"][0]["sourcePreorderId"] == preorder_id

    confirmed_event = next(event for event in memory.list_events() if event["eventName"] == "order.confirmed")
    assert confirmed_event["payload"]["linkedPreorderIds"] == [preorder_id]


def test_order_create_route_rejects_missing_source_preorder() -> None:
    customer_id = _create_customer()

    response = client.post(
        "/api/v1/orders",
        json={
            "customerId": customer_id,
            "channel": "direct",
            "lines": [
                {
                    "productSkuId": "sku-1",
                    "orderedQty": 1,
                    "unit": "kg",
                    "sourcePreorderId": "missing-preorder-id",
                }
            ],
            "meta": {
                "correlationId": "corr-api-order-invalid-preorder",
                "idempotencyKey": "idem-api-order-invalid-preorder",
            },
        },
    )

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "NOT_FOUND"
    assert body["message"] == "Preorder missing-preorder-id not found."


def test_order_allocation_adjust_and_release_routes() -> None:
    customer_id = _create_customer()
    preorder_id = _create_preorder(customer_id)
    _seed_released_lot(lot_id="lot-api-1", available_qty=10)

    created = client.post(
        "/api/v1/orders",
        json={
            "customerId": customer_id,
            "channel": "direct",
            "lines": [
                {
                    "productSkuId": "sku-1",
                    "orderedQty": 4,
                    "unit": "kg",
                    "sourcePreorderId": preorder_id,
                }
            ],
            "meta": {
                "correlationId": "corr-api-adjust-order-create",
                "idempotencyKey": "idem-api-adjust-order-create",
            },
        },
    )
    assert created.status_code == 201
    order_id = created.json()["data"]["orderId"]
    order_line_id = created.json()["data"]["lines"][0]["orderLineId"]

    confirmed = client.post(
        f"/api/v1/orders/{order_id}/confirm",
        json={"meta": {"correlationId": "corr-api-adjust-order-confirm", "idempotencyKey": "idem-api-adjust-order-confirm"}},
    )
    assert confirmed.status_code == 200

    allocated = client.post(
        f"/api/v1/orders/{order_id}/allocate",
        json={
            "allocations": [
                {"orderLineId": order_line_id, "lotId": "lot-api-1", "allocatedQty": 4}
            ],
            "meta": {"correlationId": "corr-api-adjust-order-allocate", "idempotencyKey": "idem-api-adjust-order-allocate"},
        },
    )
    assert allocated.status_code == 200
    allocation_id = allocated.json()["allocations"][0]["allocationId"]

    adjusted = client.post(
        f"/api/v1/orders/{order_id}/allocations/{allocation_id}/adjust",
        json={
            "newAllocatedQty": 2,
            "reason": "customer_reduced_qty",
            "meta": {"correlationId": "corr-api-adjust-order-adjust", "idempotencyKey": "idem-api-adjust-order-adjust"},
        },
    )
    assert adjusted.status_code == 200
    adjusted_body = adjusted.json()
    assert adjusted_body["orderStatus"] == "partially_allocated"
    assert adjusted_body["allocation"]["allocatedQty"] == 2
    assert adjusted_body["allocation"]["status"] == "active"

    released = client.post(
        f"/api/v1/orders/{order_id}/allocations/{allocation_id}/release",
        json={
            "reason": "lot_reassigned",
            "meta": {"correlationId": "corr-api-adjust-order-release", "idempotencyKey": "idem-api-adjust-order-release"},
        },
    )
    assert released.status_code == 200
    released_body = released.json()
    assert released_body["orderStatus"] == "confirmed"
    assert released_body["allocation"]["status"] == "released"