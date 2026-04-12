# pyright: reportMissingImports=false
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import audit as audit_store


client = TestClient(app)


def test_audit_endpoint_filters_by_target_and_decision() -> None:
    audit_store.append_audit_log(
        {
            "auditId": "audit-api-1",
            "actorId": "sales-1",
            "actorRole": "sales",
            "actionName": "order.allocate",
            "targetType": "Order",
            "targetId": "order-1",
            "decision": "denied",
            "reasonCode": "insufficient_lot_qty",
            "correlationId": "corr-api-1",
            "createdAt": "2026-04-12T08:00:00+00:00",
            "metadata": {"lotId": "lot-1"},
        }
    )
    audit_store.append_audit_log(
        {
            "auditId": "audit-api-2",
            "actorId": "sales-1",
            "actorRole": "sales",
            "actionName": "order.allocate",
            "targetType": "Order",
            "targetId": "order-1",
            "decision": "allowed",
            "correlationId": "corr-api-2",
            "createdAt": "2026-04-12T09:00:00+00:00",
        }
    )

    response = client.get(
        "/api/v1/audit",
        params={"targetType": "Order", "targetId": "order-1", "decision": "denied"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["auditId"] == "audit-api-1"
    assert payload["items"][0]["reasonCode"] == "insufficient_lot_qty"
    assert payload["items"][0]["metadata"]["lotId"] == "lot-1"


def test_audit_endpoint_filters_by_correlation_actor_and_time_range() -> None:
    audit_store.append_audit_log(
        {
            "auditId": "audit-api-3",
            "actorId": "ops-1",
            "actorRole": "ops",
            "actionName": "lot.release",
            "targetType": "Lot",
            "targetId": "lot-1",
            "decision": "allowed",
            "correlationId": "corr-audit",
            "createdAt": "2026-04-12T10:00:00+00:00",
        }
    )
    audit_store.append_audit_log(
        {
            "auditId": "audit-api-4",
            "actorId": "ops-1",
            "actorRole": "ops",
            "actionName": "lot.block",
            "targetType": "Lot",
            "targetId": "lot-1",
            "decision": "allowed",
            "correlationId": "corr-audit",
            "createdAt": "2026-04-12T11:00:00+00:00",
        }
    )

    response = client.get(
        "/api/v1/audit",
        params={
            "correlationId": "corr-audit",
            "actorId": "ops-1",
            "actorRole": "ops",
            "from": "2026-04-12T10:30:00+00:00",
            "to": "2026-04-12T11:30:00+00:00",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] == 1
    assert payload["items"][0]["auditId"] == "audit-api-4"
    assert payload["items"][0]["actionName"] == "lot.block"


def test_audit_endpoint_rejects_invalid_datetime_filter_with_error_envelope() -> None:
    response = client.get("/api/v1/audit", params={"from": "not-a-datetime"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["code"] == "VALIDATION_ERROR"
    assert payload["message"] == "Request validation failed"
    assert payload["details"]["errors"]