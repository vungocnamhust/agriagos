from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.project_cost_records import CreateProjectCostRecordRequest
from app.services import project_cost_records as project_cost_record_service
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


def _bind_postgres_project_cost_record_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(project_cost_record_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_cost_record_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
            "name": "Cost Record Org",
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
            "name": "Cost Scope",
        },
    )


def _seed_project_assignment(
    postgres_db_session: Session,
    project_assignment_id: str,
    project_scope_id: str,
    target_id: str,
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
                'lot',
                CAST(:target_id AS uuid),
                true,
                1,
                '{}'::jsonb
            )
            """
        ),
        {
            "project_assignment_id": project_assignment_id,
            "project_scope_id": project_scope_id,
            "target_id": target_id,
        },
    )


def _seed_confirmed_contribution(
    postgres_db_session: Session,
    contribution_id: str,
    project_scope_id: str,
    project_assignment_id: str,
    organization_id: str,
    target_id: str,
) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_contribution_events (
                project_contribution_event_id,
                project_scope_id,
                project_assignment_id,
                organization_id,
                actor_id,
                subject_type,
                subject_id,
                contribution_type,
                role,
                quantity,
                unit,
                estimated_value,
                currency,
                status,
                confirmed_by,
                confirmed_at,
                source,
                metadata_json,
                created_at,
                updated_at
            ) VALUES (
                CAST(:project_contribution_event_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:project_assignment_id AS uuid),
                CAST(:organization_id AS uuid),
                :actor_id,
                'lot',
                CAST(:subject_id AS uuid),
                'labor_day',
                'producer',
                1,
                'day',
                100000,
                'VND',
                'confirmed',
                'admin-1',
                CAST(:confirmed_at AS timestamptz),
                'manual',
                '{}'::jsonb,
                CAST(:confirmed_at AS timestamptz),
                CAST(:confirmed_at AS timestamptz)
            )
            """
        ),
        {
            "project_contribution_event_id": contribution_id,
            "project_scope_id": project_scope_id,
            "project_assignment_id": project_assignment_id,
            "organization_id": organization_id,
            "actor_id": f"actor-{contribution_id[-6:]}",
            "subject_id": target_id,
            "confirmed_at": "2026-04-16T08:00:00+00:00",
        },
    )


@pytest.mark.postgres_integration
def test_project_cost_record_persists_and_lists_in_recognized_order_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # This validates the runtime PostgreSQL path after the migration chain has
    # settled, including the listing index that serves the cost-record query.
    _bind_postgres_project_cost_record_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    target_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    assignment_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    contribution_ids = [str(uuid.uuid4()), str(uuid.uuid4())]

    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)
    for assignment_id, target_id, contribution_id in zip(assignment_ids, target_ids, contribution_ids, strict=True):
        _seed_project_assignment(postgres_db_session, assignment_id, project_scope_id, target_id)
        _seed_confirmed_contribution(
            postgres_db_session,
            contribution_id,
            project_scope_id,
            assignment_id,
            organization_id,
            target_id,
        )

    older = project_cost_record_service.create_project_cost_record(
        project_scope_id,
        CreateProjectCostRecordRequest(
            costType="labor_payout",
            amount=450000,
            currency="VND",
            recognizedAt="2026-04-15T10:00:00Z",
            sourceObjectType="project_contribution_event",
            sourceObjectId=contribution_ids[0],
            attributionPolicy="direct_source_link",
            meta=Meta(
                correlationId="corr-pg-project-cost-create-1",
                idempotencyKey="idem-pg-project-cost-create-1",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )
    newer = project_cost_record_service.create_project_cost_record(
        project_scope_id,
        CreateProjectCostRecordRequest(
            costType="labor_payout",
            amount=550000,
            currency="VND",
            recognizedAt="2026-04-16T10:00:00Z",
            sourceObjectType="project_contribution_event",
            sourceObjectId=contribution_ids[1],
            attributionPolicy="direct_source_link",
            meta=Meta(
                correlationId="corr-pg-project-cost-create-2",
                idempotencyKey="idem-pg-project-cost-create-2",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    listed = project_cost_record_service.list_project_cost_records_for_actor(
        project_scope_id,
        meta=Meta(actorId="acct-pg-1", actorRole="accountant"),
    )

    assert [item.costRecordId for item in listed] == [newer.data.costRecordId, older.data.costRecordId]
    assert [item.amount for item in listed] == [550000.0, 450000.0]

    persisted_rows = postgres_db_session.execute(
        text(
            """
            SELECT cost_record_id, recognized_at, amount
            FROM project_cost_records
            WHERE project_scope_id = CAST(:project_scope_id AS uuid)
            ORDER BY recognized_at DESC, cost_record_id
            """
        ),
        {"project_scope_id": project_scope_id},
    ).mappings().all()

    assert [str(row["cost_record_id"]) for row in persisted_rows] == [newer.data.costRecordId, older.data.costRecordId]

    index_definition = postgres_db_session.execute(
        text(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = current_schema()
              AND tablename = 'project_cost_records'
              AND indexname = 'idx_proj_cost_scope_recognized'
            """
        )
    ).scalar_one()

    assert "project_scope_id" in index_definition
    assert "recognized_at DESC" in index_definition
    assert "cost_record_id" in index_definition