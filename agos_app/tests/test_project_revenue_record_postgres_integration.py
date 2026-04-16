from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.project_revenue_records import CreateProjectRevenueRecordRequest
from app.services import project_revenue_records as project_revenue_record_service
from app.store import _db


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_project_revenue_record_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(project_revenue_record_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_revenue_record_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
            "name": "Revenue Record Org",
        },
    )


def _seed_customer(postgres_db_session: Session, customer_id: str) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO customers (
                customer_id,
                tenant_id,
                customer_code,
                full_name,
                phone,
                phone_normalized,
                channel_source,
                status,
                tags,
                notes
            ) VALUES (
                CAST(:customer_id AS uuid),
                'default',
                :customer_code,
                :full_name,
                :phone,
                :phone_normalized,
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {
            "customer_id": customer_id,
            "customer_code": f"CUS-{customer_id[-6:].upper()}",
            "full_name": "Revenue Customer",
            "phone": "+84900000002",
            "phone_normalized": "84900000002",
        },
    )


def _seed_project_scope(postgres_db_session: Session, project_scope_id: str, organization_id: str) -> None:
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
            "project_scope_code": f"PRJ-{project_scope_id[-4:].upper()}",
            "name": "Revenue Scope",
        },
    )


def _seed_delivered_order(
    postgres_db_session: Session,
    order_id: str,
    organization_id: str,
    customer_id: str,
    delivered_at: str,
) -> None:
    product_sku_id = str(uuid.uuid4())
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (CAST(:product_sku_id AS uuid), 'default', :sku_code, 'Revenue SKU', 'kg', 'active')
            """
        ),
        {
            "product_sku_id": product_sku_id,
            "sku_code": f"SKU-{order_id[-6:].upper()}",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                order_code,
                organization_id,
                customer_id,
                channel,
                delivered_at,
                source_preorder_flag,
                status,
                payment_status,
                tenant_id
            ) VALUES (
                CAST(:order_id AS uuid),
                :order_code,
                CAST(:organization_id AS uuid),
                CAST(:customer_id AS uuid),
                'admin',
                CAST(:delivered_at AS timestamptz),
                false,
                'delivered',
                'unpaid',
                'default'
            )
            """
        ),
        {
            "order_id": order_id,
            "order_code": f"ORD-{order_id[-6:].upper()}",
            "organization_id": organization_id,
            "customer_id": customer_id,
            "delivered_at": delivered_at,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_order_lines (
                order_line_id,
                order_id,
                product_sku_id,
                ordered_qty,
                allocated_qty,
                packed_qty,
                delivered_qty,
                unit,
                status
            ) VALUES (
                CAST(:order_line_id AS uuid),
                CAST(:order_id AS uuid),
                CAST(:product_sku_id AS uuid),
                3,
                3,
                3,
                3,
                'kg',
                'delivered'
            )
            """
        ),
        {
            "order_line_id": str(uuid.uuid4()),
            "order_id": order_id,
            "product_sku_id": product_sku_id,
        },
    )


def _seed_project_assignment(
    postgres_db_session: Session,
    project_scope_id: str,
    order_id: str,
) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_assignments (
                project_assignment_id,
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                metadata_json
            ) VALUES (
                CAST(:project_assignment_id AS uuid),
                CAST(:project_scope_id AS uuid),
                'order',
                CAST(:target_id AS uuid),
                true,
                1,
                '{}'::jsonb
            )
            """
        ),
        {
            "project_assignment_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "target_id": order_id,
        },
    )


@pytest.mark.postgres_integration
def test_project_revenue_record_persists_and_lists_in_recognized_order_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_revenue_record_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    older_order_id = str(uuid.uuid4())
    newer_order_id = str(uuid.uuid4())

    _seed_organization(postgres_db_session, organization_id)
    _seed_customer(postgres_db_session, customer_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)
    _seed_delivered_order(postgres_db_session, older_order_id, organization_id, customer_id, "2026-04-15T10:00:00+00:00")
    _seed_delivered_order(postgres_db_session, newer_order_id, organization_id, customer_id, "2026-04-16T10:00:00+00:00")
    _seed_project_assignment(postgres_db_session, project_scope_id, older_order_id)
    _seed_project_assignment(postgres_db_session, project_scope_id, newer_order_id)

    older = project_revenue_record_service.create_project_revenue_record(
        project_scope_id,
        CreateProjectRevenueRecordRequest(
            revenueType="delivered_order_sale",
            grossAmount=900000,
            netAmount=850000,
            currency="VND",
            sourceObjectType="order",
            sourceObjectId=older_order_id,
            meta=Meta(
                correlationId="corr-pg-project-revenue-create-1",
                idempotencyKey="idem-pg-project-revenue-create-1",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )
    newer = project_revenue_record_service.create_project_revenue_record(
        project_scope_id,
        CreateProjectRevenueRecordRequest(
            revenueType="delivered_order_sale",
            grossAmount=1200000,
            netAmount=1100000,
            currency="VND",
            sourceObjectType="order",
            sourceObjectId=newer_order_id,
            meta=Meta(
                correlationId="corr-pg-project-revenue-create-2",
                idempotencyKey="idem-pg-project-revenue-create-2",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    listed = project_revenue_record_service.list_project_revenue_records_for_actor(
        project_scope_id,
        meta=Meta(actorId="acct-pg-1", actorRole="accountant"),
    )

    assert [item.revenueRecordId for item in listed] == [newer.data.revenueRecordId, older.data.revenueRecordId]
    assert [item.netAmount for item in listed] == [1100000.0, 850000.0]
    assert [item.customerId for item in listed] == [customer_id, customer_id]

    persisted_rows = postgres_db_session.execute(
        text(
            """
            SELECT revenue_record_id, recognized_at, net_amount, customer_id
            FROM project_revenue_records
            WHERE project_scope_id = CAST(:project_scope_id AS uuid)
            ORDER BY recognized_at DESC, revenue_record_id
            """
        ),
        {"project_scope_id": project_scope_id},
    ).mappings().all()

    assert [str(row["revenue_record_id"]) for row in persisted_rows] == [newer.data.revenueRecordId, older.data.revenueRecordId]
    assert [str(row["customer_id"]) for row in persisted_rows] == [customer_id, customer_id]

    index_definition = postgres_db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'project_revenue_records'
              AND indexname = 'idx_proj_rev_scope_recognized'
            """
        )
    ).scalar_one()

    assert "project_scope_id" in index_definition
    assert "recognized_at DESC" in index_definition
    assert "revenue_record_id" in index_definition


@pytest.mark.postgres_integration
def test_project_revenue_record_rejects_duplicate_source_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_revenue_record_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    _seed_organization(postgres_db_session, organization_id)
    _seed_customer(postgres_db_session, customer_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)
    _seed_delivered_order(postgres_db_session, order_id, organization_id, customer_id, "2026-04-16T10:00:00+00:00")
    _seed_project_assignment(postgres_db_session, project_scope_id, order_id)

    first = project_revenue_record_service.create_project_revenue_record(
        project_scope_id,
        CreateProjectRevenueRecordRequest(
            revenueType="delivered_order_sale",
            grossAmount=900000,
            netAmount=850000,
            currency="VND",
            sourceObjectType="order",
            sourceObjectId=order_id,
            meta=Meta(
                correlationId="corr-pg-project-revenue-dup-1",
                idempotencyKey="idem-pg-project-revenue-dup-1",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    assert first.data.sourceObjectId == order_id

    with pytest.raises(Exception) as exc_info:
        project_revenue_record_service.create_project_revenue_record(
            project_scope_id,
            CreateProjectRevenueRecordRequest(
                revenueType="delivered_order_sale",
                grossAmount=900000,
                netAmount=850000,
                currency="VND",
                sourceObjectType="order",
                sourceObjectId=order_id,
                meta=Meta(
                    correlationId="corr-pg-project-revenue-dup-2",
                    idempotencyKey="idem-pg-project-revenue-dup-2",
                    actorId="admin-pg-1",
                    actorRole="admin",
                ),
            ),
        )

    from fastapi import HTTPException

    assert isinstance(exc_info.value, HTTPException)
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Revenue source order already has a revenue record for this project scope."