from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.project_contributions import (
    ConfirmProjectContributionRequest,
    RecordProjectContributionRequest,
    RejectProjectContributionRequest,
)
from app.services import project_contributions as project_contribution_service
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


def _bind_postgres_project_contribution_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(project_contribution_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_contribution_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
            "name": "Contribution Org",
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
            "name": "Contribution Scope",
        },
    )


def _seed_project_assignment(
    postgres_db_session: Session,
    project_assignment_id: str,
    project_scope_id: str,
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
            "target_id": str(uuid.uuid4()),
        },
    )


@pytest.mark.postgres_integration
def test_project_contribution_persists_full_lifecycle_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_contribution_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    assignment_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)
    _seed_project_assignment(postgres_db_session, assignment_id, project_scope_id)

    created = project_contribution_service.record_project_contribution(
        project_scope_id,
        RecordProjectContributionRequest(
            projectAssignmentId=assignment_id,
            organizationId=organization_id,
            actorId=str(uuid.uuid4()),
            subjectType="lot",
            subjectId=project_contribution_service._get_project_assignment_record_or_404(assignment_id)["targetId"],
            contributionType="labor_day",
            role="producer",
            quantity=3,
            unit="day",
            estimatedValue=750000,
            currency="VND",
            meta=Meta(
                correlationId="corr-pg-project-contribution-create",
                idempotencyKey="idem-pg-project-contribution-create",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    confirmed = project_contribution_service.confirm_project_contribution(
        project_scope_id,
        created.data.projectContributionEventId,
        ConfirmProjectContributionRequest(
            meta=Meta(
                correlationId="corr-pg-project-contribution-confirm",
                idempotencyKey="idem-pg-project-contribution-confirm",
                actorId="admin-pg-1",
                actorRole="admin",
            )
        ),
    )

    second_created = project_contribution_service.record_project_contribution(
        project_scope_id,
        RecordProjectContributionRequest(
            projectAssignmentId=assignment_id,
            organizationId=organization_id,
            actorId=str(uuid.uuid4()),
            subjectType="lot",
            subjectId=project_contribution_service._get_project_assignment_record_or_404(assignment_id)["targetId"],
            contributionType="cash_support",
            role="supporter",
            quantity=1,
            unit="entry",
            estimatedValue=250000,
            currency="VND",
            meta=Meta(
                correlationId="corr-pg-project-contribution-create-2",
                idempotencyKey="idem-pg-project-contribution-create-2",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    rejected = project_contribution_service.reject_project_contribution(
        project_scope_id,
        second_created.data.projectContributionEventId,
        RejectProjectContributionRequest(
            reason="duplicate entry",
            meta=Meta(
                correlationId="corr-pg-project-contribution-reject",
                idempotencyKey="idem-pg-project-contribution-reject",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    listed = project_contribution_service.list_project_contributions_for_actor(
        project_scope_id,
        meta=Meta(actorId="admin-pg-1", actorRole="admin"),
    )

    assert confirmed.data.status.value == "confirmed"
    assert rejected.data.status.value == "rejected"
    assert [item.status.value for item in listed] == ["confirmed", "rejected"]

    rows = postgres_db_session.execute(
        text(
            """
            SELECT
                project_contribution_event_id,
                status,
                confirmed_by,
                confirmed_at,
                rejection_reason,
                estimated_value,
                currency
            FROM project_contribution_events
            WHERE project_scope_id = CAST(:project_scope_id AS uuid)
            ORDER BY created_at, project_contribution_event_id
            """
        ),
        {"project_scope_id": project_scope_id},
    ).mappings().all()

    assert [row["status"] for row in rows] == ["confirmed", "rejected"]
    assert rows[0]["confirmed_by"] == "admin-pg-1"
    assert rows[0]["confirmed_at"] is not None
    assert rows[1]["rejection_reason"] == "duplicate entry"
    assert [float(row["estimated_value"]) for row in rows] == [750000.0, 250000.0]
    assert [row["currency"] for row in rows] == ["VND", "VND"]

    event_rows = postgres_db_session.execute(
        text(
            """
            SELECT event_name, payload
            FROM domain_events
            WHERE aggregate_type = 'ProjectContributionEvent'
                            AND aggregate_id IN (:first_id, :second_id)
            ORDER BY occurred_at, event_id
            """
        ),
        {
            "first_id": created.data.projectContributionEventId,
            "second_id": second_created.data.projectContributionEventId,
        },
    ).mappings().all()

    assert [row["event_name"] for row in event_rows] == [
        "project_contribution.recorded",
        "project_contribution.confirmed",
        "project_contribution.recorded",
        "project_contribution.rejected",
    ]


@pytest.mark.postgres_integration
def test_project_contribution_rejects_unknown_assignment_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_contribution_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)

    with pytest.raises(Exception):
        project_contribution_service.record_project_contribution(
            project_scope_id,
            RecordProjectContributionRequest(
                projectAssignmentId=str(uuid.uuid4()),
                organizationId=organization_id,
                actorId=str(uuid.uuid4()),
                subjectType="lot",
                subjectId=str(uuid.uuid4()),
                contributionType="labor_day",
                role="producer",
                quantity=1,
                unit="day",
                estimatedValue=100000,
                currency="VND",
                meta=Meta(
                    correlationId="corr-pg-project-contribution-missing",
                    idempotencyKey="idem-pg-project-contribution-missing",
                    actorId="admin-pg-1",
                    actorRole="admin",
                ),
            ),
        )

    persisted = postgres_db_session.execute(
        text("SELECT count(*) FROM project_contribution_events WHERE project_scope_id = CAST(:project_scope_id AS uuid)"),
        {"project_scope_id": project_scope_id},
    ).scalar_one()
    assert persisted == 0