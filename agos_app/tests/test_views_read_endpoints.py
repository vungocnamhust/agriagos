# pyright: reportMissingImports=false, reportPrivateUsage=false
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


def test_customer_360_returns_not_found_error_for_unknown_customer() -> None:
    response = client.get("/api/v1/views/customer-360/missing-customer", headers=_auth_headers(actor_role="sales", actor_id="sales-1"))

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"
    assert response.json()["message"] == "Customer not found."


def test_customer_360_returns_customer_preorders_orders_and_preferences() -> None:
    memory.save_customer(
        "customer-1",
        {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "createdAt": "2026-04-11T00:00:00Z",
            "tags": ["vip"],
            "channelSource": "zalo",
            "defaultAddress": "Da Lat",
            "district": "Ward 1",
            "province": "Lam Dong",
            "notes": "Priority customer",
            "lastOrderAt": "2026-04-12T08:00:00Z",
        },
    )
    memory.save_preorder(
        "preorder-1",
        {
            "preorderId": "preorder-1",
            "preorderCode": "DT-002",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 20.0,
            "allocatedQty": 5.0,
            "deliveredQty": 2.0,
            "cancelledQty": 0.0,
            "remainingQty": 13.0,
            "status": "active",
        },
    )
    memory.save_preorder(
        "preorder-2",
        {
            "preorderId": "preorder-2",
            "preorderCode": "DT-001",
            "customerId": "customer-1",
            "productSkuId": "sku-2",
            "committedQty": 10.0,
            "allocatedQty": 0.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": 10.0,
            "status": "active",
        },
    )
    memory.save_order(
        "order-1",
        {
            "orderId": "order-1",
            "orderCode": "ORD-202604-0002",
            "customerId": "customer-1",
            "channel": "direct",
            "status": "confirmed",
            "paymentStatus": "unpaid",
            "deliveryDateExpected": "2026-04-15",
            "lines": [
                {
                    "orderLineId": "line-1",
                    "productSkuId": "sku-1",
                    "orderedQty": 5.0,
                    "allocatedQty": 0.0,
                    "packedQty": 0.0,
                    "deliveredQty": 0.0,
                    "unit": "kg",
                    "status": "open",
                }
            ],
        },
    )
    memory.save_order(
        "order-2",
        {
            "orderId": "order-2",
            "orderCode": "ORD-202604-0001",
            "customerId": "customer-1",
            "channel": "crm",
            "status": "delivered",
            "paymentStatus": "paid",
            "deliveryDateExpected": "2026-04-10",
            "lines": [],
        },
    )
    memory.save_customer_preferences(
        "customer-1",
        [
            {
                "preferenceType": "variety",
                "preferenceValue": "jasmine",
                "confidenceLevel": 0.7,
            },
            {
                "preferenceType": "pack_size",
                "preferenceValue": "5kg",
                "confidenceLevel": 0.9,
            },
        ],
    )

    response = client.get("/api/v1/views/customer-360/customer-1", headers=_auth_headers(actor_role="sales", actor_id="sales-1"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["fullName"] == "Alice Nguyen"
    assert [item["preorderCode"] for item in payload["activePreorders"]] == ["DT-002", "DT-001"]
    assert payload["activePreorders"][0]["remainingQty"] == 13.0
    assert [item["orderCode"] for item in payload["recentOrders"]] == ["ORD-202604-0002", "ORD-202604-0001"]
    assert [item["preferenceType"] for item in payload["preferences"]] == ["pack_size", "variety"]


def test_available_lots_board_only_returns_released_positive_qty_lots() -> None:
    memory.save_lot(
        "lot-1",
        {
            "lotId": "lot-1",
            "lotCode": "LOT-001",
            "productSkuId": "sku-1",
            "releasedQty": 10.0,
            "availableQty": 6.0,
            "status": "released",
        },
    )
    memory.save_lot(
        "lot-2",
        {
            "lotId": "lot-2",
            "lotCode": "LOT-002",
            "productSkuId": "sku-1",
            "releasedQty": 10.0,
            "availableQty": 0.0,
            "status": "released",
        },
    )
    memory.save_lot(
        "lot-3",
        {
            "lotId": "lot-3",
            "lotCode": "LOT-003",
            "productSkuId": "sku-2",
            "releasedQty": 4.0,
            "availableQty": 4.0,
            "status": "blocked",
        },
    )

    response = client.get("/api/v1/views/available-lots", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 200
    assert [item["lotCode"] for item in response.json()["items"]] == ["LOT-001"]


def test_pending_fulfillment_returns_phase1_statuses_sorted_by_deadline() -> None:
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    memory.save_customer("customer-2", {"customerId": "customer-2", "fullName": "Bao"})
    memory.save_order(
        "order-1",
        {
            "orderId": "order-1",
            "orderCode": "ORD-003",
            "customerId": "customer-1",
            "channel": "direct",
            "status": "packed",
            "paymentStatus": "unpaid",
            "deliveryDateExpected": None,
            "lines": [],
        },
    )
    memory.save_order(
        "order-2",
        {
            "orderId": "order-2",
            "orderCode": "ORD-001",
            "customerId": "customer-2",
            "channel": "direct",
            "status": "confirmed",
            "paymentStatus": "unpaid",
            "deliveryDateExpected": "2026-04-13",
            "lines": [],
        },
    )
    memory.save_order(
        "order-3",
        {
            "orderId": "order-3",
            "orderCode": "ORD-002",
            "customerId": "customer-1",
            "channel": "direct",
            "status": "delivered",
            "paymentStatus": "paid",
            "deliveryDateExpected": "2026-04-12",
            "lines": [],
        },
    )

    response = client.get("/api/v1/views/pending-fulfillment", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 200
    payload = response.json()["items"]
    assert [item["orderCode"] for item in payload] == ["ORD-001", "ORD-003"]
    assert [item["status"] for item in payload] == ["confirmed", "packed"]


def test_farm_view_returns_legacy_plot_and_cycle_lists() -> None:
    memory.save_plot("plot-1", {
        "plotId": "plot-1",
        "plotCode": "PLOT-001",
        "organizationId": "org-1",
        "name": "Garden A",
        "locationText": "Da Lat",
        "areaValue": 2.5,
        "areaUnit": "ha",
        "status": "active",
    })
    memory.save_crop_cycle("cycle-1", {
        "cropCycleId": "cycle-1",
        "plotId": "plot-1",
        "organizationId": "org-1",
        "cropName": "Strawberry",
        "growthStage": "maturing",
        "status": "active",
        "expectedHarvestFrom": "2026-05-01",
        "expectedHarvestTo": "2026-05-10",
    })

    response = client.get("/api/v1/views/farm", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["plots"]) == 1
    assert len(payload["cropCycles"]) == 1
    assert payload["plots"][0]["plotCode"] == "PLOT-001"
    assert payload["plots"][0]["organizationId"] == "org-1"
    assert payload["cropCycles"][0]["organizationId"] == "org-1"


def test_farm_summary_board_flattens_plot_and_active_cycle_rows() -> None:
    memory.save_plot("plot-1", {
        "plotId": "plot-1",
        "plotCode": "PLOT-001",
        "organizationId": "org-1",
        "name": "Garden A",
        "locationText": "Da Lat",
        "areaValue": 2.5,
        "areaUnit": "ha",
        "status": "active",
    })
    memory.save_plot("plot-2", {
        "plotId": "plot-2",
        "plotCode": "PLOT-002",
        "organizationId": None,
        "name": "Garden B",
        "locationText": "Bao Loc",
        "areaValue": 1.0,
        "areaUnit": "ha",
        "status": "active",
    })
    memory.save_crop_cycle("cycle-1", {
        "cropCycleId": "cycle-1",
        "plotId": "plot-1",
        "organizationId": "org-1",
        "cropName": "Strawberry",
        "growthStage": "flowering_or_maturing",
        "status": "active",
        "expectedHarvestFrom": "2026-05-01",
        "expectedHarvestTo": "2026-05-10",
        "estimatedYieldQty": 120.0,
    })
    memory.save_crop_cycle("cycle-2", {
        "cropCycleId": "cycle-2",
        "plotId": "plot-1",
        "cropName": "Spinach",
        "growthStage": "growing",
        "status": "closed",
        "expectedHarvestFrom": "2026-04-01",
        "expectedHarvestTo": "2026-04-05",
        "estimatedYieldQty": 50.0,
    })

    response = client.get("/api/v1/views/farm-summary-board", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 200
    payload = response.json()["items"]
    assert [item["plotCode"] for item in payload] == ["PLOT-001", "PLOT-002"]
    assert payload[0]["growthStage"] == "maturing"
    assert payload[0]["plotOrganizationId"] == "org-1"
    assert payload[0]["cropCycleOrganizationId"] == "org-1"
    assert payload[1]["cropCycleId"] is None
    assert payload[1]["plotOrganizationId"] is None
    assert payload[1]["cropCycleOrganizationId"] is None


def test_customer_360_rejects_viewer_and_records_denied_audit() -> None:
    response = client.get("/api/v1/views/customer-360/customer-1", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to read Customer 360 views."
    assert memory.list_audit_logs()[-1]["actionName"] == "view.customer_360"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_customer_360_view"