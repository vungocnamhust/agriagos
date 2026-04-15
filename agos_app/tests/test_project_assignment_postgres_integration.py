from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import gateway
from app.models.common import Meta
from app.models.enums import ProjectAssignmentTargetType
from app.models.project_assignments import CreateProjectAssignmentRequest, EndProjectAssignmentRequest
from app.services import project_assignments as project_assignment_service
from app.store import _db
from app.store import project_assignments as project_assignment_store


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_project_assignment_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(gateway, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_assignment_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_assignment_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
            "name": "Project Assignment Org",
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
            "name": "Lua mua 2026",
        },
    )


def _seed_customer_and_sku(postgres_db_session: Session) -> tuple[str, str]:
    customer_id = str(uuid.uuid4())
    product_sku_id = str(uuid.uuid4())
    suffix = customer_id[-6:].upper()
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
                'Project Assignment Customer',
                '+84900000002',
                '84900000002',
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {
            "customer_id": customer_id,
            "customer_code": f"KH-ASG-{suffix}",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (
                product_sku_id,
                tenant_id,
                sku_code,
                sku_name,
                unit,
                status
            ) VALUES (
                CAST(:product_sku_id AS uuid),
                'default',
                :sku_code,
                'Assignment SKU',
                'kg',
                'active'
            )
            """
        ),
        {
            "product_sku_id": product_sku_id,
            "sku_code": f"SKU-ASG-{suffix}",
        },
    )
    return customer_id, product_sku_id


def _seed_farm_and_commercial_targets(
    postgres_db_session: Session,
    *,
    organization_id: str,
    customer_id: str,
    product_sku_id: str,
) -> dict[str, str]:
    plot_id = str(uuid.uuid4())
    crop_cycle_id = str(uuid.uuid4())
    lot_id = str(uuid.uuid4())
    preorder_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())

    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (
                plot_id,
                plot_code,
                name,
                location_text,
                area_value,
                area_unit,
                status,
                organization_id
            ) VALUES (
                CAST(:plot_id AS uuid),
                'PLOT-ASG-001',
                'Vuon A1',
                'Lam Dong',
                2.5,
                'ha',
                'active',
                CAST(:organization_id AS uuid)
            )
            """
        ),
        {"plot_id": plot_id, "organization_id": organization_id},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO crop_cycles (
                crop_cycle_id,
                plot_id,
                crop_name,
                start_date,
                growth_stage,
                status,
                organization_id
            ) VALUES (
                CAST(:crop_cycle_id AS uuid),
                CAST(:plot_id AS uuid),
                'Lua',
                CURRENT_DATE,
                'growing',
                'active',
                CAST(:organization_id AS uuid)
            )
            """
        ),
        {
            "crop_cycle_id": crop_cycle_id,
            "plot_id": plot_id,
            "organization_id": organization_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                tenant_id,
                lot_code,
                product_sku_id,
                source_type,
                source_ref_id,
                harvest_or_production_date,
                actual_qty,
                available_qty,
                reserved_qty,
                released_qty,
                status,
                organization_id
            ) VALUES (
                CAST(:lot_id AS uuid),
                'default',
                'LOT-ASG-001',
                CAST(:product_sku_id AS uuid),
                'crop_cycle',
                :source_ref_id,
                now(),
                10,
                10,
                0,
                10,
                'released',
                CAST(:organization_id AS uuid)
            )
            """
        ),
        {
            "lot_id": lot_id,
            "product_sku_id": product_sku_id,
            "source_ref_id": crop_cycle_id,
            "organization_id": organization_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO preorders (
                preorder_id,
                tenant_id,
                preorder_code,
                customer_id,
                product_sku_id,
                committed_qty,
                allocated_qty,
                delivered_qty,
                cancelled_qty,
                remaining_qty,
                delivery_cadence,
                status,
                start_date,
                updated_at,
                organization_id
            ) VALUES (
                CAST(:preorder_id AS uuid),
                'default',
                'DT-ASG-001',
                CAST(:customer_id AS uuid),
                CAST(:product_sku_id AS uuid),
                10,
                0,
                0,
                0,
                10,
                'weekly',
                'active',
                CURRENT_DATE,
                now(),
                CAST(:organization_id AS uuid)
            )
            """
        ),
        {
            "preorder_id": preorder_id,
            "customer_id": customer_id,
            "product_sku_id": product_sku_id,
            "organization_id": organization_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                tenant_id,
                order_code,
                customer_id,
                channel,
                status,
                payment_status,
                organization_id
            ) VALUES (
                CAST(:order_id AS uuid),
                'default',
                'ORD-ASG-001',
                CAST(:customer_id AS uuid),
                'web',
                'confirmed',
                'unpaid',
                CAST(:organization_id AS uuid)
            )
            """
        ),
        {
            "order_id": order_id,
            "customer_id": customer_id,
            "organization_id": organization_id,
        },
    )

    return {
        "plot": plot_id,
        "crop_cycle": crop_cycle_id,
        "lot": lot_id,
        "preorder": preorder_id,
        "order": order_id,
    }


@pytest.mark.postgres_integration
def test_project_assignment_core_persists_supported_targets_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_assignment_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)
    customer_id, product_sku_id = _seed_customer_and_sku(postgres_db_session)
    targets = _seed_farm_and_commercial_targets(
        postgres_db_session,
        organization_id=organization_id,
        customer_id=customer_id,
        product_sku_id=product_sku_id,
    )

    created_assignment_ids: list[str] = []
    for index, target_type in enumerate(
        (
            ProjectAssignmentTargetType.plot,
            ProjectAssignmentTargetType.crop_cycle,
            ProjectAssignmentTargetType.lot,
            ProjectAssignmentTargetType.preorder,
            ProjectAssignmentTargetType.order,
        )
    ):
        created = project_assignment_service.create_project_assignment(
            project_scope_id,
            CreateProjectAssignmentRequest(
                targetType=target_type,
                targetId=targets[target_type.value],
                isPrimary=index == 0,
                attributionWeight=1.0 if index == 0 else 0.5,
                metadata={"lane": target_type.value},
                meta=Meta(
                    correlationId=f"corr-pg-project-assignment-create-{index}",
                    idempotencyKey=f"idem-pg-project-assignment-create-{index}",
                    actorId="admin-pg-1",
                    actorRole="admin",
                ),
            ),
        )
        created_assignment_ids.append(created.data.projectAssignmentId)
        assert created.data.targetType.value == target_type.value
        assert created.data.targetId == targets[target_type.value]

    listed = project_assignment_service.list_project_assignments_for_actor(
        project_scope_id,
        meta=Meta(actorId="admin-pg-1", actorRole="admin"),
    )
    assert [item.targetType.value for item in listed] == [
        "plot",
        "crop_cycle",
        "lot",
        "preorder",
        "order",
    ]

    ended = project_assignment_service.end_project_assignment(
        project_scope_id,
        created_assignment_ids[0],
        EndProjectAssignmentRequest(
            reason="season completed",
            meta=Meta(
                correlationId="corr-pg-project-assignment-end",
                idempotencyKey="idem-pg-project-assignment-end",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )
    assert ended.data.endedReason == "season completed"
    assert ended.data.endedAt is not None

    fetched = project_assignment_store.fetch_project_assignment(created_assignment_ids[0])
    assert fetched is not None
    assert fetched["targetType"] == "plot"
    assert fetched["endedReason"] == "season completed"

    persisted = postgres_db_session.execute(
        text(
            """
            SELECT
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                ended_reason,
                metadata_json
            FROM project_assignments
            WHERE project_assignment_id = CAST(:project_assignment_id AS uuid)
            """
        ),
        {"project_assignment_id": created_assignment_ids[0]},
    ).mappings().one()

    assert str(persisted["project_scope_id"]) == project_scope_id
    assert persisted["target_type"] == "plot"
    assert str(persisted["target_id"]) == targets["plot"]
    assert persisted["is_primary"] is True
    assert float(persisted["attribution_weight"]) == 1.0
    assert persisted["ended_reason"] == "season completed"
    assert dict(persisted["metadata_json"]) == {"lane": "plot"}
