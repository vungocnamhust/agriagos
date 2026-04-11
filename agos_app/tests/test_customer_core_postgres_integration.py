# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.customers import CreateCustomerRequest, ReviewDuplicateCandidateRequest, UpdateCustomerRequest, UpsertPreferenceRequest
from app.services import customers as customer_service
from app.store import _db
from app.store import customers as customer_store


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


@pytest.mark.postgres_integration
def test_customer_core_persists_normalized_phone_preferences_and_duplicate_candidates(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(customer_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(customer_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))

    first = customer_service.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900 111 222",
            province="Lam Dong",
            meta=Meta(correlationId="corr-pg-create-1", idempotencyKey="idem-pg-create-1", actorId="sales-1", actorRole="sales"),
        )
    )
    second = customer_service.create_customer(
        CreateCustomerRequest(
            fullName="Alice Nguyen",
            phone="0900 111 333",
            province="Lam Dong",
            meta=Meta(correlationId="corr-pg-create-2", idempotencyKey="idem-pg-create-2", actorId="sales-1", actorRole="sales"),
        )
    )

    matches = customer_service.list_customers("+84 900111222", None, None)
    assert [item["customerId"] for item in matches] == [first.data.customerId]

    preference = customer_service.upsert_preference(
        first.data.customerId,
        UpsertPreferenceRequest(
            preferenceType="variety",
            preferenceValue="jasmine",
            source="integration",
            confidenceLevel=0.95,
            meta=Meta(
                correlationId="corr-pg-pref",
                actorId="trusted-sync",
                actorRole="integration",
                externalRef="crm:pref:pg-1",
            ),
        ),
    )
    assert preference.confirmedBy == "trusted-sync"
    assert preference.confirmedAt is not None

    updated = customer_service.update_customer(
        first.data.customerId,
        UpdateCustomerRequest(
            notes="postgres update",
            tags=["vip", "priority"],
            meta=Meta(correlationId="corr-pg-update", idempotencyKey="idem-pg-update", actorId="sales-1", actorRole="sales"),
        ),
    )
    assert updated.notes == "postgres update"
    assert updated.tags == ["vip", "priority"]
    assert updated.preferences[0].confirmedBy == "trusted-sync"

    candidates = customer_service.list_customer_duplicate_candidates(first.data.customerId)
    assert len(candidates) == 1
    assert {candidates[0].primaryCustomerId, candidates[0].suspectedCustomerId} == {
        first.data.customerId,
        second.data.customerId,
    }

    reviewed = customer_service.review_duplicate_candidate(
        candidates[0].candidateId,
        ReviewDuplicateCandidateRequest(
            status="reviewed_distinct",
            note="different household",
            meta=Meta(correlationId="corr-pg-review", actorId="sales-1", actorRole="sales"),
        ),
    )
    assert reviewed.status == "reviewed_distinct"
    assert reviewed.reviewedBy == "sales-1"

    fetched = customer_store.fetch_customer(first.data.customerId)
    assert fetched is not None
    assert fetched["phoneNormalized"] == "0900111222"
