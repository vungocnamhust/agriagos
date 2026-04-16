from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.common import Meta
from app.models.project_revenue_records import CreateProjectRevenueRecordRequest
from app.services import project_revenue_records as revenue_record_service
from app.store import memory


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


def _seed_project_scope(project_scope_id: str) -> None:
    memory.save_project_scope(
        project_scope_id,
        {
            "projectScopeId": project_scope_id,
            "organizationId": "org-1",
            "projectScopeCode": "PRJ-202604-0100",
            "name": "Revenue Scope",
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def _seed_order(*, order_id: str, status: str, delivered_at: str | None) -> None:
    memory.save_order(
        order_id,
        {
            "orderId": order_id,
            "tenantId": "default",
            "orderCode": f"ORD-{order_id[-6:].upper()}",
            "organizationId": "org-1",
            "customerId": "cust-1",
            "channel": "direct",
            "deliveryDateExpected": None,
            "shippingAddress": None,
            "carrier": None,
            "trackingRef": None,
            "shippedAt": "2026-04-16T08:00:00Z" if delivered_at else None,
            "deliveredAt": delivered_at,
            "proofRef": None,
            "failureReason": None,
            "deliveryNote": None,
            "paymentIntent": None,
            "note": None,
            "sourcePreorderFlag": False,
            "status": status,
            "paymentStatus": "unpaid",
            "version": 1,
            "lines": [
                {
                    "orderLineId": f"line-{order_id[-6:]}",
                    "productSkuId": "sku-1",
                    "orderedQty": 3.0,
                    "allocatedQty": 3.0,
                    "packedQty": 3.0,
                    "deliveredQty": 3.0 if delivered_at else 0.0,
                    "unit": "kg",
                    "sourcePreorderId": None,
                    "status": "delivered" if delivered_at else "open",
                }
            ],
        },
    )


def _seed_project_assignment(project_scope_id: str, order_id: str, *, ended_at: str | None = None) -> None:
    memory.save_project_assignment(
        f"assignment-{order_id}",
        {
            "projectAssignmentId": f"assignment-{order_id}",
            "projectScopeId": project_scope_id,
            "targetType": "order",
            "targetId": order_id,
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": ended_at,
            "endedReason": "ended" if ended_at else None,
            "metadata": {"lane": "commercial"},
        },
    )


def test_project_revenue_record_routes_record_and_list_revenues() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000d401"
    order_id = "00000000-0000-0000-0000-00000000d402"
    _seed_project_scope(project_scope_id)
    _seed_order(order_id=order_id, status="delivered", delivered_at="2026-04-16T10:00:00Z")
    _seed_project_assignment(project_scope_id, order_id)

    created = client.post(
        f"/api/v1/projects/{project_scope_id}/revenue-records",
        json={
            "revenueType": "delivered_order_sale",
            "grossAmount": 900000,
            "netAmount": 850000,
            "currency": "VND",
            "sourceObjectType": "order",
            "sourceObjectId": order_id,
            "meta": {
                "correlationId": "corr-project-revenue-create",
                "idempotencyKey": "idem-project-revenue-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert created.status_code == 201
    payload = created.json()["data"]
    assert payload["projectScopeId"] == project_scope_id
    assert payload["organizationId"] == "org-1"
    assert payload["customerId"] == "cust-1"
    assert payload["revenueType"] == "delivered_order_sale"
    assert payload["grossAmount"] == 900000.0
    assert payload["netAmount"] == 850000.0
    assert payload["recognizedAt"] == "2026-04-16T10:00:00Z"
    assert payload["sourceObjectId"] == order_id

    listed = client.get(
        f"/api/v1/projects/{project_scope_id}/revenue-records",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["revenueRecordId"] == payload["revenueRecordId"]


def test_project_revenue_record_routes_reject_missing_undelivered_or_unassigned_orders() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000d403"
    missing_order_id = "00000000-0000-0000-0000-00000000d499"
    undelivered_order_id = "00000000-0000-0000-0000-00000000d404"
    unassigned_order_id = "00000000-0000-0000-0000-00000000d405"
    ended_assignment_order_id = "00000000-0000-0000-0000-00000000d406"

    _seed_project_scope(project_scope_id)
    _seed_order(order_id=undelivered_order_id, status="shipped", delivered_at=None)
    _seed_project_assignment(project_scope_id, undelivered_order_id)
    _seed_order(order_id=unassigned_order_id, status="delivered", delivered_at="2026-04-16T12:00:00Z")
    _seed_order(order_id=ended_assignment_order_id, status="delivered", delivered_at="2026-04-16T13:00:00Z")
    _seed_project_assignment(project_scope_id, ended_assignment_order_id, ended_at="2026-04-16T13:05:00Z")

    for order_id, expected_status, expected_message in [
        (missing_order_id, 404, "Revenue source order not found."),
        (undelivered_order_id, 422, "Revenue source order must be delivered."),
        (unassigned_order_id, 422, "Revenue source order must be actively assigned to the project scope."),
        (ended_assignment_order_id, 422, "Revenue source order must be actively assigned to the project scope."),
    ]:
        response = client.post(
            f"/api/v1/projects/{project_scope_id}/revenue-records",
            json={
                "revenueType": "delivered_order_sale",
                "grossAmount": 900000,
                "netAmount": 850000,
                "currency": "VND",
                "sourceObjectType": "order",
                "sourceObjectId": order_id,
                "meta": {
                    "correlationId": f"corr-project-revenue-{order_id[-4:]}",
                    "idempotencyKey": f"idem-project-revenue-{order_id[-4:]}",
                    "actorId": "admin-1",
                    "actorRole": "admin",
                },
            },
        )
        assert response.status_code == expected_status
        assert response.json()["message"] == expected_message


def test_project_revenue_record_routes_reject_duplicate_source_and_invalid_amounts() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000d409"
    order_id = "00000000-0000-0000-0000-00000000d410"
    _seed_project_scope(project_scope_id)
    _seed_order(order_id=order_id, status="delivered", delivered_at="2026-04-16T10:00:00Z")
    _seed_project_assignment(project_scope_id, order_id)

    first = client.post(
        f"/api/v1/projects/{project_scope_id}/revenue-records",
        json={
            "revenueType": "delivered_order_sale",
            "grossAmount": 900000,
            "netAmount": 850000,
            "currency": "VND",
            "sourceObjectType": "order",
            "sourceObjectId": order_id,
            "meta": {
                "correlationId": "corr-project-revenue-dup-first",
                "idempotencyKey": "idem-project-revenue-dup-first",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        f"/api/v1/projects/{project_scope_id}/revenue-records",
        json={
            "revenueType": "delivered_order_sale",
            "grossAmount": 900000,
            "netAmount": 850000,
            "currency": "VND",
            "sourceObjectType": "order",
            "sourceObjectId": order_id,
            "meta": {
                "correlationId": "corr-project-revenue-dup-second",
                "idempotencyKey": "idem-project-revenue-dup-second",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["message"] == "Revenue source order already has a revenue record for this project scope."

    invalid_amounts = client.post(
        f"/api/v1/projects/{project_scope_id}/revenue-records",
        json={
            "revenueType": "delivered_order_sale",
            "grossAmount": 800000,
            "netAmount": 850000,
            "currency": "VND",
            "sourceObjectType": "order",
            "sourceObjectId": "00000000-0000-0000-0000-00000000d411",
            "meta": {
                "correlationId": "corr-project-revenue-invalid-amounts",
                "idempotencyKey": "idem-project-revenue-invalid-amounts",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert invalid_amounts.status_code == 422
    assert invalid_amounts.json()["message"] == "Gross amount must be greater than or equal to net amount."


def test_project_revenue_record_service_validates_order_after_transaction_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000d407"
    order_id = "00000000-0000-0000-0000-00000000d408"
    transaction_entered = False

    @contextmanager
    def _fake_transaction():
        nonlocal transaction_entered
        transaction_entered = True
        yield

    def _get_scope_or_404(_: str) -> dict[str, str]:
        return {"organizationId": "org-1"}

    def _get_order_or_404(_: str) -> dict[str, str]:
        assert transaction_entered is True
        return {
            "orderId": order_id,
            "organizationId": "org-1",
            "customerId": "cust-1",
            "status": "delivered",
            "deliveredAt": "2026-04-16T10:00:00Z",
        }

    monkeypatch.setattr(revenue_record_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(revenue_record_service, "postgres_transaction", _fake_transaction)
    monkeypatch.setattr(revenue_record_service, "_get_project_scope_record_or_404", _get_scope_or_404)
    monkeypatch.setattr(revenue_record_service, "_get_order_record_or_404", _get_order_or_404)
    monkeypatch.setattr(revenue_record_service, "_has_active_project_scope_assignment", lambda *args, **kwargs: True)
    monkeypatch.setattr(revenue_record_service.project_revenue_record_store, "upsert_project_revenue_record", lambda record: None)
    monkeypatch.setattr(revenue_record_service.events, "emit", lambda **kwargs: {"eventName": kwargs["event_name"]})
    monkeypatch.setattr(revenue_record_service, "append_audit_decision", lambda **kwargs: None)
    monkeypatch.setattr(revenue_record_service, "check_idempotency", lambda key: None)
    monkeypatch.setattr(revenue_record_service, "record_idempotency", lambda *args, **kwargs: None)

    response = revenue_record_service.create_project_revenue_record(
        project_scope_id,
        CreateProjectRevenueRecordRequest(
            revenueType="delivered_order_sale",
            grossAmount=900000,
            netAmount=850000,
            currency="VND",
            sourceObjectType="order",
            sourceObjectId=order_id,
            meta=Meta(
                correlationId="corr-project-revenue-ordering",
                idempotencyKey="idem-project-revenue-ordering",
                actorId="admin-1",
                actorRole="admin",
            ),
        ),
    )

    assert transaction_entered is True
    assert response.data.projectScopeId == project_scope_id
    assert response.data.customerId == "cust-1"