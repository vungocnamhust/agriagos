from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.customers import (
    CreateCustomerRequest,
    ReviewDuplicateCandidateRequest,
    UpdateCustomerRequest,
    UpsertPreferenceRequest,
)
from app.services import customers
from app.store import memory


def test_create_customer_records_event_audit_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    response = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000001",
            tags=["vip"],
            meta=Meta(correlationId="corr-customer", idempotencyKey="idem-customer", actorId="sales-1", actorRole="sales"),
        )
    )

    assert memory.get_customer(response.data.customerId) is not None
    assert memory.list_events()[-1]["eventName"] == "customer.created"
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.create"
    assert memory.list_audit_logs()[-1]["decision"] == "allowed"
    assert memory.get_idempotent_result("idem-customer")["data"]["customerId"] == response.data.customerId


def test_create_customer_rejects_unauthorized_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        customers.create_customer(
            CreateCustomerRequest(
                fullName="Alice Nguyen",
                phone="0900000999",
                meta=Meta(correlationId="corr-customer-deny", idempotencyKey="idem-customer-deny", actorId="ops-1", actorRole="ops"),
            )
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_customer_creation"


def test_create_customer_rejects_disabled_bypass_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        customers.create_customer(
            CreateCustomerRequest(
                fullName="Alice Nguyen",
                phone="0900000888",
                meta=Meta(
                    correlationId="corr-customer-bypass",
                    actorId="agent-1",
                    actorRole="agent",
                    bypassRequested=True,
                    delegatedActorRole="sales",
                ),
            )
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["reasonCode"] == "agent_execution_not_allowed"


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


def test_create_customer_rejects_duplicate_normalized_phone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)

    customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900 000 001",
            meta=Meta(correlationId="corr-customer-1", idempotencyKey="idem-customer-1", actorId="sales-1", actorRole="sales"),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        customers.create_customer(
            CreateCustomerRequest(
                fullName="Alice Duplicate",
                phone="+84 900000001",
                meta=Meta(correlationId="corr-customer-2", idempotencyKey="idem-customer-2", actorId="sales-1", actorRole="sales"),
            )
        )

    assert exc_info.value.status_code == 409
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "duplicate_phone"


def test_upsert_preference_rejects_ai_suggestion_for_canonical_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "tags": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        customers.upsert_preference(
            "customer-1",
            UpsertPreferenceRequest(
                preferenceType="variety",
                preferenceValue="jasmine",
                source="ai_suggestion",
                confidenceLevel=0.7,
                meta=Meta(correlationId="corr-pref-ai"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.preference_upsert"
    assert memory.list_audit_logs()[-1]["targetId"] == "customer-1"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "invalid_preference_source"


def test_upsert_preference_rejects_untrusted_integration_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "tags": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        customers.upsert_preference(
            "customer-1",
            UpsertPreferenceRequest(
                preferenceType="variety",
                preferenceValue="jasmine",
                source="integration",
                confidenceLevel=0.9,
                meta=Meta(correlationId="corr-pref-integration-deny", actorId="sync-1", actorRole="integration"),
            ),
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["reasonCode"] == "untrusted_integration_source"


def test_upsert_preference_allows_trusted_integration_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "tags": [],
        },
    )

    response = customers.upsert_preference(
        "customer-1",
        UpsertPreferenceRequest(
            preferenceType="variety",
            preferenceValue="jasmine",
            source="integration",
            confidenceLevel=0.9,
            meta=Meta(
                correlationId="corr-pref-integration-allow",
                actorId="trusted-sync",
                actorRole="integration",
                externalRef="crm:pref:1",
            ),
        ),
    )

    assert response.source == "integration"
    assert response.confirmedBy == "trusted-sync"
    assert response.confirmedAt is not None


def test_upsert_preference_rejects_unauthorized_human_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {
            "customerId": "customer-1",
            "customerCode": "KH-001",
            "fullName": "Alice Nguyen",
            "phone": "0900000001",
            "status": "active",
            "tags": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        customers.upsert_preference(
            "customer-1",
            UpsertPreferenceRequest(
                preferenceType="variety",
                preferenceValue="jasmine",
                source="human",
                confidenceLevel=1.0,
                meta=Meta(correlationId="corr-pref-human-deny", actorId="ops-1", actorRole="ops"),
            ),
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_preference_confirmation"


def test_review_duplicate_candidate_rejects_unauthorized_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    first = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000015",
            province="Lam Dong",
                meta=Meta(correlationId="corr-review-first", idempotencyKey="idem-review-first", actorId="sales-1", actorRole="sales"),
        )
    )
    customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000016",
            province="Lam Dong",
            meta=Meta(correlationId="corr-review-second", idempotencyKey="idem-review-second", actorId="sales-1", actorRole="sales"),
        )
    )
    candidate = customers.list_customer_duplicate_candidates(first.data.customerId)[0]

    with pytest.raises(HTTPException) as exc_info:
        customers.review_duplicate_candidate(
            candidate.candidateId,
            ReviewDuplicateCandidateRequest(
                status="reviewed_distinct",
                note="Different households",
                meta=Meta(correlationId="corr-review-deny", actorId="ops-1", actorRole="ops"),
            ),
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_duplicate_candidate_review"


def test_update_customer_records_event_and_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    created = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000011",
            province="Lam Dong",
            tags=["vip"],
            meta=Meta(correlationId="corr-create-update", idempotencyKey="idem-create-update", actorId="sales-1", actorRole="sales"),
        )
    )

    updated = customers.update_customer(
        created.data.customerId,
        UpdateCustomerRequest(
            notes="Updated by sales",
            tags=["vip", "priority"],
            meta=Meta(correlationId="corr-update", idempotencyKey="idem-update", actorId="sales-1", actorRole="sales"),
        ),
    )

    assert updated.notes == "Updated by sales"
    assert updated.tags == ["vip", "priority"]
    assert memory.list_events()[-1]["eventName"] == "customer.updated"
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.update"
    assert memory.list_audit_logs()[-1]["decision"] == "allowed"


def test_update_customer_rejects_unauthorized_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    created = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000021",
            province="Lam Dong",
            meta=Meta(correlationId="corr-create-update-deny", idempotencyKey="idem-create-update-deny", actorId="sales-1", actorRole="sales"),
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        customers.update_customer(
            created.data.customerId,
            UpdateCustomerRequest(
                notes="ops should not edit customer core",
                meta=Meta(correlationId="corr-update-deny", idempotencyKey="idem-update-deny", actorId="ops-1", actorRole="ops"),
            ),
        )

    assert exc_info.value.status_code == 403
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.update"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_customer_update"


def test_list_customers_matches_keyword_against_customer_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    created = customers.create_customer(
        CreateCustomerRequest(
            fullName="Bao Tran",
            phone="0900000012",
            meta=Meta(correlationId="corr-create-search", idempotencyKey="idem-create-search", actorId="sales-1", actorRole="sales"),
        )
    )

    matches = customers.list_customers(None, created.data.customerCode, None)

    assert len(matches) == 1
    assert matches[0]["customerId"] == created.data.customerId


def test_get_customer_returns_preferences_and_duplicate_candidates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    first = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000013",
            province="Lam Dong",
            meta=Meta(correlationId="corr-create-first", idempotencyKey="idem-create-first", actorId="sales-1", actorRole="sales"),
        )
    )
    customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000014",
            province="Lam Dong",
            meta=Meta(correlationId="corr-create-second", idempotencyKey="idem-create-second", actorId="sales-1", actorRole="sales"),
        )
    )
    customers.upsert_preference(
        first.data.customerId,
        UpsertPreferenceRequest(
            preferenceType="variety",
            preferenceValue="jasmine",
            source="human",
            confidenceLevel=1.0,
            meta=Meta(correlationId="corr-pref-human", actorId="sales-1", actorRole="sales"),
        ),
    )

    detail = customers.get_customer(first.data.customerId)

    assert detail.preferences[0].preferenceType == "variety"
    assert detail.duplicateCandidates
    assert detail.duplicateCandidates[0].status == "open"


def test_review_duplicate_candidate_updates_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    first = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000015",
            province="Lam Dong",
            meta=Meta(correlationId="corr-review-first", idempotencyKey="idem-review-first", actorId="sales-1", actorRole="sales"),
        )
    )
    customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000016",
            province="Lam Dong",
            meta=Meta(correlationId="corr-review-second", idempotencyKey="idem-review-second", actorId="sales-1", actorRole="sales"),
        )
    )
    candidate = customers.list_customer_duplicate_candidates(first.data.customerId)[0]

    reviewed = customers.review_duplicate_candidate(
        candidate.candidateId,
        ReviewDuplicateCandidateRequest(
            status="reviewed_distinct",
            note="Different households",
            meta=Meta(correlationId="corr-review", actorId="sales-1", actorRole="sales"),
        ),
    )

    assert reviewed.status == "reviewed_distinct"
    assert reviewed.reviewedBy == "sales-1"
    assert memory.list_audit_logs()[-1]["actionName"] == "customer.duplicate_candidate_review"


def test_update_customer_notes_does_not_duplicate_open_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(customers, "postgres_enabled", lambda: False)
    first = customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000017",
            province="Lam Dong",
            meta=Meta(correlationId="corr-dup-refresh-first", idempotencyKey="idem-dup-refresh-first", actorId="sales-1", actorRole="sales"),
        )
    )
    customers.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900000018",
            province="Lam Dong",
            meta=Meta(correlationId="corr-dup-refresh-second", idempotencyKey="idem-dup-refresh-second", actorId="sales-1", actorRole="sales"),
        )
    )

    before_candidates = customers.list_customer_duplicate_candidates(first.data.customerId)
    customers.update_customer(
        first.data.customerId,
        UpdateCustomerRequest(
            notes="notes only update",
            meta=Meta(correlationId="corr-dup-refresh-update", idempotencyKey="idem-dup-refresh-update", actorId="sales-1", actorRole="sales"),
        ),
    )
    after_candidates = customers.list_customer_duplicate_candidates(first.data.customerId)

    assert len(before_candidates) == 1
    assert len(after_candidates) == 1
