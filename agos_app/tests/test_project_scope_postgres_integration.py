from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import gateway
from app.models.common import Meta
from app.models.enums import ProjectScopeType
from app.models.project_scopes import ActivateProjectScopeRequest, CreateProjectScopeRequest, UpdateProjectScopeRequest
from app.services import project_scopes as project_scope_service
from app.store import _db
from app.store import project_scopes as project_scope_store


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_project_scope_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(gateway, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_scope_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_scope_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
            "name": "Project Scope Org",
        },
    )


@pytest.mark.postgres_integration
def test_project_scope_core_persists_create_update_and_status_transition_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_project_scope_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)

    created = project_scope_service.create_project_scope(
        CreateProjectScopeRequest(
            organizationId=organization_id,
            name="Lua mua 2026",
            projectScopeType=ProjectScopeType.value_stream,
            seasonYear="2026",
            ownerActorId="founder-1",
            description="Value stream cho lua mua 2026",
            metadata={"channel": "seasonal", "region": "Lam Dong"},
            meta=Meta(
                correlationId="corr-pg-project-create",
                idempotencyKey="idem-pg-project-create",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        )
    )

    updated = project_scope_service.update_project_scope(
        created.data.projectScopeId,
        UpdateProjectScopeRequest(
            description="Updated project scope",
            metadata={"channel": "seasonal", "phase": "commercial"},
            meta=Meta(
                correlationId="corr-pg-project-update",
                idempotencyKey="idem-pg-project-update",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    activated = project_scope_service.activate_project_scope(
        created.data.projectScopeId,
        ActivateProjectScopeRequest(
            meta=Meta(
                correlationId="corr-pg-project-activate",
                idempotencyKey="idem-pg-project-activate",
                actorId="admin-pg-1",
                actorRole="admin",
            )
        ),
    )

    fetched = project_scope_store.fetch_project_scope(created.data.projectScopeId)
    assert fetched is not None
    assert created.data.projectScopeCode.startswith("PRJ-")
    assert updated.data.description == "Updated project scope"
    assert activated.data.status.value == "active"
    assert fetched["status"] == "active"
    assert fetched["metadata"] == {"channel": "seasonal", "phase": "commercial"}

    persisted = postgres_db_session.execute(
        text(
            """
            SELECT
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                description,
                metadata_json
            FROM project_scopes
            WHERE project_scope_id = CAST(:project_scope_id AS uuid)
            """
        ),
        {"project_scope_id": created.data.projectScopeId},
    ).mappings().one()

    assert str(persisted["organization_id"]) == organization_id
    assert persisted["project_scope_code"] == created.data.projectScopeCode
    assert persisted["name"] == "Lua mua 2026"
    assert persisted["project_scope_type"] == "value_stream"
    assert persisted["status"] == "active"
    assert persisted["season_year"] == "2026"
    assert persisted["owner_actor_id"] == "founder-1"
    assert persisted["description"] == "Updated project scope"
    assert dict(persisted["metadata_json"]) == {"channel": "seasonal", "phase": "commercial"}
