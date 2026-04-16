from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

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


@pytest.mark.postgres_integration
def test_actor_identity_and_affiliation_routes_persist_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import actor_authority as actor_authority_service
    from app.services import organizations as organization_service
    from app.services import project_scopes as project_scope_service

    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(actor_authority_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(actor_authority_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))
    monkeypatch.setattr(organization_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(project_scope_service, "postgres_enabled", lambda: True)

    client = TestClient(app)

    organization_response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Actor PG Org",
            "organizationType": "household_producer",
            "meta": {
                "correlationId": "corr-actor-pg-org-create",
                "idempotencyKey": "idem-actor-pg-org-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert organization_response.status_code == 201
    organization_id = organization_response.json()["data"]["organizationId"]

    project_response = client.post(
        "/api/v1/projects",
        json={
            "organizationId": organization_id,
            "name": "Actor PG Project",
            "projectScopeType": "value_stream",
            "meta": {
                "correlationId": "corr-actor-pg-project-create",
                "idempotencyKey": "idem-actor-pg-project-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert project_response.status_code == 201
    project_scope_id = project_response.json()["data"]["projectScopeId"]

    actor_response = client.post(
        "/api/v1/actors",
        headers={"X-Actor-Id": "admin-1", "X-Actor-Role": "admin"},
        json={
            "actorType": "person",
            "displayName": "Actor PG User",
            "primaryEmail": "actor-pg@example.com",
            "meta": {
                "correlationId": "corr-actor-pg-create",
                "idempotencyKey": "idem-actor-pg-create",
            },
        },
    )

    assert actor_response.status_code == 201
    actor_id = actor_response.json()["data"]["actorId"]

    affiliation_response = client.post(
        "/api/v1/affiliations",
        headers={"X-Actor-Id": "admin-1", "X-Actor-Role": "admin"},
        json={
            "actorId": actor_id,
            "organizationId": organization_id,
            "projectScopeId": project_scope_id,
            "affiliationKind": "membership",
            "effectiveAt": "2026-04-16T10:00:00Z",
            "meta": {
                "correlationId": "corr-affiliation-pg-create",
                "idempotencyKey": "idem-affiliation-pg-create",
            },
        },
    )

    assert affiliation_response.status_code == 201
    actor_row = postgres_db_session.execute(
        text(
            """
            SELECT actor_code, actor_type, display_name, status, primary_email
            FROM actor_identities
            WHERE actor_id = :actor_id
            """
        ),
        {"actor_id": actor_id},
    ).mappings().one()
    assert actor_row["actor_code"].startswith("ACT-")
    assert actor_row["actor_type"] == "person"
    assert actor_row["display_name"] == "Actor PG User"
    assert actor_row["status"] == "active"
    assert actor_row["primary_email"] == "actor-pg@example.com"

    affiliation_row = postgres_db_session.execute(
        text(
            """
            SELECT actor_id, organization_id, project_scope_id, affiliation_kind, status
            FROM actor_affiliations
            WHERE actor_id = :actor_id
            """
        ),
        {"actor_id": actor_id},
    ).mappings().one()
    assert str(affiliation_row["actor_id"]) == actor_id
    assert str(affiliation_row["organization_id"]) == organization_id
    assert str(affiliation_row["project_scope_id"]) == project_scope_id
    assert affiliation_row["affiliation_kind"] == "membership"
    assert affiliation_row["status"] == "active"