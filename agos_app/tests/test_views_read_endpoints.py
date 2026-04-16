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
            "organizationId": "org-001",
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
            "organizationId": "org-001",
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
            "organizationId": "org-001",
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
            "organizationId": "org-001",
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
    assert [item["organizationId"] for item in payload["activePreorders"]] == ["org-001", "org-001"]
    assert payload["activePreorders"][0]["remainingQty"] == 13.0
    assert [item["orderCode"] for item in payload["recentOrders"]] == ["ORD-202604-0002", "ORD-202604-0001"]
    assert [item["organizationId"] for item in payload["recentOrders"]] == ["org-001", "org-001"]
    assert [item["preferenceType"] for item in payload["preferences"]] == ["pack_size", "variety"]


def test_available_lots_board_only_returns_released_positive_qty_lots() -> None:
    memory.save_lot(
        "lot-1",
        {
            "lotId": "lot-1",
            "lotCode": "LOT-001",
            "organizationId": "org-lot-view-1",
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
    assert response.json()["items"][0]["organizationId"] == "org-lot-view-1"


def test_pending_fulfillment_returns_phase1_statuses_sorted_by_deadline() -> None:
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    memory.save_customer("customer-2", {"customerId": "customer-2", "fullName": "Bao"})
    memory.save_order(
        "order-1",
        {
            "orderId": "order-1",
            "orderCode": "ORD-003",
            "organizationId": "org-pending-1",
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
            "organizationId": None,
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
    assert [item["organizationId"] for item in payload] == [None, "org-pending-1"]


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


def test_project_pnl_summary_returns_operational_totals_per_scope() -> None:
    memory.save_project_scope(
        "scope-1",
        {
            "projectScopeId": "scope-1",
            "projectScopeCode": "PRJ-001",
            "name": "Scope One",
            "organizationId": "org-1",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_scope(
        "scope-2",
        {
            "projectScopeId": "scope-2",
            "projectScopeCode": "PRJ-002",
            "name": "Scope Two",
            "organizationId": "org-2",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_cost_record(
        "cost-1",
        {
            "costRecordId": "cost-1",
            "projectScopeId": "scope-1",
            "amount": 400000.0,
            "currency": "VND",
        },
    )
    memory.save_project_cost_record(
        "cost-2",
        {
            "costRecordId": "cost-2",
            "projectScopeId": "scope-1",
            "amount": 150000.0,
            "currency": "VND",
        },
    )
    memory.save_project_revenue_record(
        "rev-1",
        {
            "revenueRecordId": "rev-1",
            "projectScopeId": "scope-1",
            "netAmount": 900000.0,
            "currency": "VND",
        },
    )
    memory.save_project_revenue_record(
        "rev-2",
        {
            "revenueRecordId": "rev-2",
            "projectScopeId": "scope-2",
            "netAmount": 300000.0,
            "currency": "USD",
        },
    )

    response = client.get(
        "/api/v1/views/project-pnl-summary",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert [item["projectScopeCode"] for item in payload] == ["PRJ-001", "PRJ-002"]
    assert payload[0]["costRecordCount"] == 2
    assert payload[0]["revenueRecordCount"] == 1
    assert payload[0]["recognizedCostAmount"] == 550000.0
    assert payload[0]["recognizedRevenueNetAmount"] == 900000.0
    assert payload[0]["marginAmount"] == 350000.0
    assert payload[0]["currency"] == "VND"
    assert payload[1]["costRecordCount"] == 0
    assert payload[1]["revenueRecordCount"] == 1
    assert payload[1]["recognizedCostAmount"] == 0.0
    assert payload[1]["recognizedRevenueNetAmount"] == 300000.0
    assert payload[1]["marginAmount"] == 300000.0
    assert payload[1]["currency"] == "USD"


def test_project_pnl_summary_returns_empty_items_when_no_financial_records_exist() -> None:
    memory.save_project_scope(
        "scope-empty",
        {
            "projectScopeId": "scope-empty",
            "projectScopeCode": "PRJ-EMPTY",
            "name": "Empty Scope",
            "organizationId": "org-empty",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )

    response = client.get(
        "/api/v1/views/project-pnl-summary",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_project_pnl_summary_nulls_currency_when_scope_has_mixed_financial_currencies() -> None:
    memory.save_project_scope(
        "scope-mixed",
        {
            "projectScopeId": "scope-mixed",
            "projectScopeCode": "PRJ-MIXED",
            "name": "Mixed Currency Scope",
            "organizationId": "org-mixed",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_cost_record(
        "cost-mixed",
        {
            "costRecordId": "cost-mixed",
            "projectScopeId": "scope-mixed",
            "amount": 100000.0,
            "currency": "VND",
        },
    )
    memory.save_project_revenue_record(
        "rev-mixed",
        {
            "revenueRecordId": "rev-mixed",
            "projectScopeId": "scope-mixed",
            "netAmount": 50.0,
            "currency": "USD",
        },
    )

    response = client.get(
        "/api/v1/views/project-pnl-summary",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["projectScopeCode"] == "PRJ-MIXED"
    assert payload[0]["recognizedCostAmount"] == 100000.0
    assert payload[0]["recognizedRevenueNetAmount"] == 50.0
    assert payload[0]["marginAmount"] == -99950.0
    assert payload[0]["currency"] is None


def test_project_order_allocation_summary_returns_operational_totals_per_scope() -> None:
    memory.save_project_scope(
        "scope-alloc",
        {
            "projectScopeId": "scope-alloc",
            "projectScopeCode": "PRJ-ALLOC",
            "name": "Allocation Scope",
            "organizationId": "org-alloc",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_assignment(
        "assignment-order-alloc-1",
        {
            "projectAssignmentId": "assignment-order-alloc-1",
            "projectScopeId": "scope-alloc",
            "targetType": "order",
            "targetId": "order-alloc-1",
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": None,
            "endedReason": None,
            "metadata": {},
        },
    )
    memory.save_order(
        "order-alloc-1",
        {
            "orderId": "order-alloc-1",
            "orderCode": "ORD-ALLOC-001",
            "organizationId": "org-alloc",
            "customerId": "customer-alloc-1",
            "channel": "direct",
            "status": "allocated",
            "paymentStatus": "unpaid",
            "lines": [
                {
                    "orderLineId": "line-alloc-1",
                    "productSkuId": "sku-alloc-1",
                    "orderedQty": 5.0,
                    "allocatedQty": 5.0,
                    "packedQty": 0.0,
                    "deliveredQty": 0.0,
                    "unit": "kg",
                    "status": "allocated",
                }
            ],
        },
    )
    memory.save_allocations(
        "order-alloc-1",
        [
            {
                "allocationId": "allocation-1",
                "orderLineId": "line-alloc-1",
                "lotId": "lot-alloc-1",
                "allocatedQty": 3.0,
                "status": "active",
            },
            {
                "allocationId": "allocation-2",
                "orderLineId": "line-alloc-1",
                "lotId": "lot-alloc-2",
                "allocatedQty": 2.0,
                "status": "released",
            },
        ],
    )

    response = client.get(
        "/api/v1/views/project-order-allocation-summary",
        headers=_auth_headers(actor_role="ops", actor_id="ops-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["projectScopeCode"] == "PRJ-ALLOC"
    assert payload[0]["assignedOrderCount"] == 1
    assert payload[0]["allocatedOrderCount"] == 1
    assert payload[0]["allocationCount"] == 2
    assert payload[0]["activeAllocationCount"] == 1
    assert payload[0]["releasedAllocationCount"] == 1
    assert payload[0]["allocatedQty"] == 5.0
    assert payload[0]["activeAllocatedQty"] == 3.0
    assert payload[0]["releasedAllocatedQty"] == 2.0
    assert payload[0]["unit"] == "kg"


def test_project_pnl_summary_denies_non_finance_roles() -> None:
    response = client.get(
        "/api/v1/views/project-pnl-summary",
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to read project P&L summary boards."
    assert memory.list_audit_logs()[-1]["actionName"] == "view.project_pnl_summary"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_project_pnl_summary_view"


def test_project_order_allocation_summary_denies_unauthorized_roles() -> None:
    response = client.get(
        "/api/v1/views/project-order-allocation-summary",
        headers=_auth_headers(actor_role="farm_manager", actor_id="farm-1"),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to read project order allocation summary boards."
    assert memory.list_audit_logs()[-1]["actionName"] == "view.project_order_allocation_summary"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_project_order_allocation_summary_view"


def test_project_contribution_ledger_returns_cross_scope_rows_with_assignment_context() -> None:
    memory.save_project_scope(
        "scope-ledger-1",
        {
            "projectScopeId": "scope-ledger-1",
            "projectScopeCode": "PRJ-LEDGER-001",
            "name": "Ledger Scope One",
            "organizationId": "org-ledger-1",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_scope(
        "scope-ledger-2",
        {
            "projectScopeId": "scope-ledger-2",
            "projectScopeCode": "PRJ-LEDGER-002",
            "name": "Ledger Scope Two",
            "organizationId": "org-ledger-2",
            "projectScopeType": "value_stream",
            "status": "active",
        },
    )
    memory.save_project_assignment(
        "assignment-ledger-1",
        {
            "projectAssignmentId": "assignment-ledger-1",
            "projectScopeId": "scope-ledger-1",
            "targetType": "order",
            "targetId": "order-ledger-1",
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": "2026-04-16T08:00:00Z",
            "endedAt": None,
            "endedReason": None,
            "metadata": {"lane": "commercial"},
        },
    )
    memory.save_project_assignment(
        "assignment-ledger-2",
        {
            "projectAssignmentId": "assignment-ledger-2",
            "projectScopeId": "scope-ledger-2",
            "targetType": "lot",
            "targetId": "lot-ledger-2",
            "isPrimary": True,
            "attributionWeight": 0.5,
            "createdAt": "2026-04-16T09:00:00Z",
            "endedAt": None,
            "endedReason": None,
            "metadata": {"lane": "farm"},
        },
    )
    memory.save_project_contribution(
        "contribution-ledger-2",
        {
            "projectContributionEventId": "contribution-ledger-2",
            "projectScopeId": "scope-ledger-2",
            "projectAssignmentId": "assignment-ledger-2",
            "organizationId": "org-ledger-2",
            "actorId": "producer-2",
            "actorType": "person",
            "subjectType": "lot",
            "subjectId": "lot-ledger-2",
            "contributionType": "labor_day",
            "role": "producer",
            "verificationStatus": "verified",
            "verificationSource": "admin_confirmed",
            "verificationNote": None,
            "verificationEvidenceRef": None,
            "quantity": 1.0,
            "unit": "day",
            "estimatedValue": None,
            "currency": None,
            "status": "confirmed",
            "confirmedBy": "admin-2",
            "confirmedAt": "2026-04-16T10:30:00Z",
            "rejectionReason": None,
            "source": "manual",
            "metadata": {},
            "createdAt": "2026-04-16T10:00:00Z",
        },
    )
    memory.save_project_contribution(
        "contribution-ledger-1",
        {
            "projectContributionEventId": "contribution-ledger-1",
            "projectScopeId": "scope-ledger-1",
            "projectAssignmentId": "assignment-ledger-1",
            "organizationId": "org-ledger-1",
            "actorId": "producer-1",
            "actorType": "partner",
            "subjectType": "order",
            "subjectId": "order-ledger-1",
            "contributionType": "cash_support",
            "role": "supporter",
            "verificationStatus": "system_detected",
            "verificationSource": "field_log",
            "verificationNote": "Imported from source note",
            "verificationEvidenceRef": "evidence-1",
            "quantity": 2.0,
            "unit": "entry",
            "estimatedValue": 350000.0,
            "currency": "VND",
            "status": "proposed",
            "confirmedBy": None,
            "confirmedAt": None,
            "rejectionReason": None,
            "source": "manual",
            "metadata": {},
            "createdAt": "2026-04-16T11:00:00Z",
        },
    )

    response = client.get(
        "/api/v1/views/project-contribution-ledger",
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert [item["projectContributionEventId"] for item in payload] == [
        "contribution-ledger-2",
        "contribution-ledger-1",
    ]
    assert payload[0]["projectScopeCode"] == "PRJ-LEDGER-002"
    assert payload[0]["assignmentTargetType"] == "lot"
    assert payload[0]["assignmentTargetId"] == "lot-ledger-2"
    assert payload[0]["status"] == "confirmed"
    assert payload[1]["projectScopeCode"] == "PRJ-LEDGER-001"
    assert payload[1]["assignmentTargetType"] == "order"
    assert payload[1]["assignmentTargetId"] == "order-ledger-1"
    assert payload[1]["estimatedValue"] == 350000.0
    assert payload[1]["currency"] == "VND"


def test_project_contribution_ledger_denies_unauthorized_roles() -> None:
    response = client.get(
        "/api/v1/views/project-contribution-ledger",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to read project contribution ledger boards."
    assert memory.list_audit_logs()[-1]["actionName"] == "view.project_contribution_ledger"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_project_contribution_ledger_view"


def test_project_scope_summary_views_reject_invalid_project_scope_id() -> None:
    contribution_response = client.get(
        "/api/v1/views/project-contribution-summary?projectScopeId=not-a-uuid",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    pnl_response = client.get(
        "/api/v1/views/project-pnl-summary?projectScopeId=not-a-uuid",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    allocation_response = client.get(
        "/api/v1/views/project-order-allocation-summary?projectScopeId=not-a-uuid",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    ledger_response = client.get(
        "/api/v1/views/project-contribution-ledger?projectScopeId=not-a-uuid",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )

    assert contribution_response.status_code == 422
    assert contribution_response.json()["message"] == "projectScopeId must be a valid UUID."
    assert pnl_response.status_code == 422
    assert pnl_response.json()["message"] == "projectScopeId must be a valid UUID."
    assert allocation_response.status_code == 422
    assert allocation_response.json()["message"] == "projectScopeId must be a valid UUID."
    assert ledger_response.status_code == 422
    assert ledger_response.json()["message"] == "projectScopeId must be a valid UUID."