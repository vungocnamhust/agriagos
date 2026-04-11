from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.customers import CreateCustomerRequest, UpsertPreferenceRequest
from app.services import customers
from app.store import memory


def test_create_customer_records_event_audit_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    response = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000001",
            tags=["vip"],
            meta=Meta(correlationId="corr-customer", idempotencyKey="idem-customer"),
        )
    )

    assert memory.get_customer(response.data.customerId) is not None
    assert memory.list_events()[-1]["eventName"] == "customer.created"
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.create"
    assert memory.list_audit_logs()[-1]["decision"] == "allowed"
    assert memory.get_idempotent_result("idem-customer")["data"]["customerId"] == response.data.customerId


def test_upsert_preference_missing_customer_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        customers.upsert_preference(
            "missing-customer",
            UpsertPreferenceRequest(
                preferenceType="rice",
                preferenceValue="jasmine",
                meta=Meta(correlationId="corr-pref"),
            ),
        )

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.preference_upsert"
    assert memory.list_audit_logs()[-1]["targetId"] == "missing-customer"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "customer_not_found"
