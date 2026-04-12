from __future__ import annotations

import pytest

from app.store import _db
from app.store import audit as audit_store


def test_query_audit_logs_filters_and_orders_results() -> None:
    audit_store.append_audit_log(
        {
            "auditId": "audit-1",
            "actorId": "sales-1",
            "actorRole": "sales",
            "actionName": "order.allocate",
            "targetType": "Order",
            "targetId": "order-1",
            "decision": "denied",
            "reasonCode": "insufficient_lot_qty",
            "correlationId": "corr-1",
            "createdAt": "2026-04-12T10:00:00+00:00",
            "metadata": {"lotId": "lot-1"},
        }
    )
    audit_store.append_audit_log(
        {
            "auditId": "audit-2",
            "actorId": "ops-1",
            "actorRole": "ops",
            "actionName": "lot.release",
            "targetType": "Lot",
            "targetId": "lot-1",
            "decision": "allowed",
            "correlationId": "corr-2",
            "createdAt": "2026-04-12T11:00:00+00:00",
        }
    )
    audit_store.append_audit_log(
        {
            "auditId": "audit-3",
            "actorId": "sales-1",
            "actorRole": "sales",
            "actionName": "order.allocate",
            "targetType": "Order",
            "targetId": "order-1",
            "decision": "denied",
            "reasonCode": "preorder_quota_exceeded",
            "correlationId": "corr-3",
            "createdAt": "2026-04-12T12:00:00+00:00",
        }
    )

    filtered = audit_store.query_audit_logs(
        target_type="Order",
        target_id="order-1",
        action_name="order.allocate",
        decision="denied",
        actor_id="sales-1",
        actor_role="sales",
        created_from="2026-04-12T10:30:00+00:00",
        created_to="2026-04-12T12:30:00+00:00",
    )

    assert [entry["auditId"] for entry in filtered] == ["audit-3"]
    assert filtered[0]["reasonCode"] == "preorder_quota_exceeded"

    by_reason = audit_store.query_audit_logs(reason_code="insufficient_lot_qty")

    assert [entry["auditId"] for entry in by_reason] == ["audit-1"]


@pytest.mark.postgres_integration
def test_query_audit_logs_reads_from_postgres(postgres_db_session) -> None:
    original_enabled = _db.is_enabled
    original_current_session = _db.current_session

    _db.is_enabled = lambda: True
    _db.current_session = lambda: postgres_db_session
    try:
        audit_store.append_audit_log(
            {
                "auditId": "00000000-0000-0000-0000-000000000001",
                "actorId": "admin-1",
                "actorRole": "admin",
                "actionName": "customer.update",
                "targetType": "Customer",
                "targetId": "customer-1",
                "decision": "allowed",
                "correlationId": "corr-pg",
                "createdAt": "2026-04-12T13:00:00+00:00",
            }
        )
        audit_store.append_audit_log(
            {
                "auditId": "00000000-0000-0000-0000-000000000002",
                "actorId": "admin-1",
                "actorRole": "admin",
                "actionName": "customer.update",
                "targetType": "Customer",
                "targetId": "customer-1",
                "decision": "denied",
                "reasonCode": "duplicate_phone",
                "correlationId": "corr-pg",
                "createdAt": "2026-04-12T13:05:00+00:00",
            }
        )

        items = audit_store.query_audit_logs(
            target_type="Customer",
            target_id="customer-1",
            correlation_id="corr-pg",
        )
    finally:
        _db.is_enabled = original_enabled
        _db.current_session = original_current_session

    assert [entry["auditId"] for entry in items] == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000001",
    ]
    assert items[0]["reasonCode"] == "duplicate_phone"