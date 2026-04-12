# pyright: reportMissingImports=false
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import audit as audit_store
from app.store import memory


client = TestClient(app)


def _auth_headers(
    *,
    actor_role: str,
    actor_id: str = "actor-1",
    bypass_requested: bool = False,
) -> dict[str, str]:
    headers = {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }
    if bypass_requested:
        headers["X-Bypass-Requested"] = "true"
    return headers


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
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
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
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
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


def test_audit_endpoint_denies_viewer_and_records_denial() -> None:
    response = client.get("/api/v1/audit", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to query the audit log."
    assert memory.list_audit_logs()[-1]["actionName"] == "audit.query"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_audit_query"


def test_audit_endpoint_allows_accountant_queries() -> None:
    audit_store.append_audit_log(
        {
            "auditId": "audit-api-5",
            "actorId": "sales-1",
            "actorRole": "sales",
            "actionName": "preorder.create",
            "targetType": "Preorder",
            "targetId": "preorder-1",
            "decision": "allowed",
            "correlationId": "corr-api-5",
            "createdAt": "2026-04-12T12:00:00+00:00",
        }
    )

    response = client.get("/api/v1/audit", headers=_auth_headers(actor_role="accountant", actor_id="acct-1"))

    assert response.status_code == 200
    assert response.json()["total"] >= 1


def test_audit_endpoint_denies_sales_queries() -> None:
    response = client.get("/api/v1/audit", headers=_auth_headers(actor_role="sales", actor_id="sales-1"))

    assert response.status_code == 403
    assert response.json()["message"] == "Actor is not allowed to query the audit log."
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_audit_query"


def test_audit_endpoint_denies_bypass_requests() -> None:
    response = client.get(
        "/api/v1/audit",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1", bypass_requested=True),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Agent bypass lane is not enabled in Phase 1."
    assert memory.list_audit_logs()[-1]["actionName"] == "audit.query"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "agent_execution_not_allowed"