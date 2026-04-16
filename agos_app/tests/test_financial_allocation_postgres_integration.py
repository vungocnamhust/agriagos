from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.financial_allocations import CreateFinancialAllocationRequest
from app.services import financial_allocations as financial_allocation_service
from app.store import _db
from app.store import financial_allocations as financial_allocation_store


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_financial_allocation_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(financial_allocation_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(financial_allocation_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


def _seed_organization(postgres_db_session: Session, organization_id: str) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                'household_producer',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": f"ORG-{organization_id[-6:].upper()}",
            "name": "Financial Allocation Org",
        },
    )


def _seed_project_scope(postgres_db_session: Session, project_scope_id: str, organization_id: str, *, code_suffix: str) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                metadata_json
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                :name,
                'value_stream',
                'active',
                '2026',
                'founder-1',
                '{}'::jsonb
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": f"PRJ-{code_suffix}",
            "name": f"Scope {code_suffix}",
        },
    )


def _seed_project_cost_record(
    postgres_db_session: Session,
    cost_record_id: str,
    project_scope_id: str,
    organization_id: str,
) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_cost_records (
                cost_record_id,
                project_scope_id,
                organization_id,
                cost_type,
                amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                attribution_policy,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (
                CAST(:cost_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'labor_payout',
                450000,
                'VND',
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz),
                'project_contribution_event',
                CAST(:source_object_id AS uuid),
                'direct_source_link',
                '{}'::jsonb,
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz),
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz)
            )
            """
        ),
        {
            "cost_record_id": cost_record_id,
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "source_object_id": str(uuid.uuid4()),
        },
    )


@pytest.mark.postgres_integration
def test_financial_allocation_persists_and_lists_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_financial_allocation_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    source_scope_id = str(uuid.uuid4())
    target_scope_id = str(uuid.uuid4())
    cost_record_id = str(uuid.uuid4())

    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, source_scope_id, organization_id, code_suffix="SRC-FA")
    _seed_project_scope(postgres_db_session, target_scope_id, organization_id, code_suffix="TGT-FA")
    _seed_project_cost_record(postgres_db_session, cost_record_id, source_scope_id, organization_id)

    created = financial_allocation_service.create_financial_allocation(
        target_scope_id,
        CreateFinancialAllocationRequest(
            sourceRecordType="cost_record",
            sourceRecordId=cost_record_id,
            allocationBasis="manual_full",
            meta=Meta(
                correlationId="corr-pg-fin-alloc-create",
                idempotencyKey="idem-pg-fin-alloc-create",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    listed = financial_allocation_store.list_financial_allocations(target_scope_id)
    fetched = financial_allocation_store.fetch_financial_allocation_by_source(target_scope_id, "cost_record", cost_record_id)

    assert created.data.projectScopeId == target_scope_id
    assert created.data.sourceRecordType == "cost_record"
    assert created.data.sourceRecordId == cost_record_id
    assert created.data.allocationBasis == "manual_full"
    assert created.data.allocationWeight == 1.0
    assert created.data.allocatedAmount == 450000.0
    assert created.data.currency == "VND"
    assert [item["financialAllocationId"] for item in listed] == [created.data.financialAllocationId]
    assert fetched is not None
    assert fetched["financialAllocationId"] == created.data.financialAllocationId

    persisted = postgres_db_session.execute(
        text(
            """
            SELECT
                project_scope_id,
                organization_id,
                source_record_type,
                source_record_id,
                allocation_basis,
                allocation_weight,
                allocated_amount,
                currency
            FROM financial_allocations
            WHERE financial_allocation_id = CAST(:financial_allocation_id AS uuid)
            """
        ),
        {"financial_allocation_id": created.data.financialAllocationId},
    ).mappings().one()

    assert str(persisted["project_scope_id"]) == target_scope_id
    assert str(persisted["organization_id"]) == organization_id
    assert persisted["source_record_type"] == "cost_record"
    assert persisted["source_record_id"] == cost_record_id
    assert persisted["allocation_basis"] == "manual_full"
    assert float(persisted["allocation_weight"]) == 1.0
    assert float(persisted["allocated_amount"]) == 450000.0
    assert persisted["currency"] == "VND"


@pytest.mark.postgres_integration
def test_financial_allocation_weighted_split_persists_across_two_scopes(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_financial_allocation_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    source_scope_id = str(uuid.uuid4())
    first_target_scope_id = str(uuid.uuid4())
    second_target_scope_id = str(uuid.uuid4())
    cost_record_id = str(uuid.uuid4())

    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, source_scope_id, organization_id, code_suffix="SRC-WFA")
    _seed_project_scope(postgres_db_session, first_target_scope_id, organization_id, code_suffix="TGT-WFA1")
    _seed_project_scope(postgres_db_session, second_target_scope_id, organization_id, code_suffix="TGT-WFA2")
    _seed_project_cost_record(postgres_db_session, cost_record_id, source_scope_id, organization_id)

    first = financial_allocation_service.create_financial_allocation(
        first_target_scope_id,
        CreateFinancialAllocationRequest(
            sourceRecordType="cost_record",
            sourceRecordId=cost_record_id,
            allocationBasis="manual_weighted",
            allocationWeight=0.6,
            meta=Meta(
                correlationId="corr-pg-fin-alloc-weighted-1",
                idempotencyKey="idem-pg-fin-alloc-weighted-1",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )
    second = financial_allocation_service.create_financial_allocation(
        second_target_scope_id,
        CreateFinancialAllocationRequest(
            sourceRecordType="cost_record",
            sourceRecordId=cost_record_id,
            allocationBasis="manual_weighted",
            allocationWeight=0.4,
            meta=Meta(
                correlationId="corr-pg-fin-alloc-weighted-2",
                idempotencyKey="idem-pg-fin-alloc-weighted-2",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    first_listed = financial_allocation_store.list_financial_allocations(first_target_scope_id)
    second_listed = financial_allocation_store.list_financial_allocations(second_target_scope_id)
    all_for_source = financial_allocation_store.list_financial_allocations_by_source_record("cost_record", cost_record_id)

    assert first.data.allocationBasis == "manual_weighted"
    assert first.data.allocationWeight == 0.6
    assert first.data.allocatedAmount == 270000.0
    assert second.data.allocationWeight == 0.4
    assert second.data.allocatedAmount == 180000.0
    assert [item["financialAllocationId"] for item in first_listed] == [first.data.financialAllocationId]
    assert [item["financialAllocationId"] for item in second_listed] == [second.data.financialAllocationId]
    assert len(all_for_source) == 2