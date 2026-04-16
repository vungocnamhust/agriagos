from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import gateway
from app.models.common import Meta
from app.models.shared_resources import (
    AllocateSharedResourceRequest,
    CreateSharedResourceRequest,
    ReleaseSharedResourceAllocationRequest,
)
from app.services import shared_resources as shared_resource_service
from app.store import _db
from app.store import shared_resources as shared_resource_store


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_shared_resource_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(gateway, "postgres_enabled", lambda: True)
    monkeypatch.setattr(shared_resource_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(shared_resource_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


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
                'family_business',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": f"ORG-{organization_id[-6:].upper()}",
            "name": "Shared Resource Org",
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
            "project_scope_code": f"PRJ-{project_scope_id[-6:].upper()}",
            "name": "Shared Resource Scope",
        },
    )


@pytest.mark.postgres_integration
def test_shared_resource_core_persists_create_and_list_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_shared_resource_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)

    created = shared_resource_service.create_shared_resource(
        CreateSharedResourceRequest(
            organizationId=organization_id,
            name="Community Warehouse",
            resourceType="warehouse",
            capacityValue=50,
            capacityUnit="ton",
            description="Shared storage for multiple scopes",
            meta=Meta(
                correlationId="corr-pg-shared-resource-create",
                idempotencyKey="idem-pg-shared-resource-create",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        )
    )

    fetched = shared_resource_store.fetch_shared_resource(created.data.sharedResourceId)
    listed = shared_resource_store.list_shared_resources()

    assert fetched is not None
    assert created.data.resourceCode.startswith("RES-")
    assert created.data.status.value == "draft"
    assert fetched["name"] == "Community Warehouse"
    assert fetched["resourceType"] == "warehouse"
    assert fetched["capacityValue"] == 50.0
    assert fetched["capacityUnit"] == "ton"
    assert [item["sharedResourceId"] for item in listed] == [created.data.sharedResourceId]

    persisted = postgres_db_session.execute(
        text(
            """
            SELECT
                organization_id,
                resource_code,
                name,
                resource_type,
                status,
                capacity_value,
                capacity_unit,
                description
            FROM shared_resources
            WHERE shared_resource_id = CAST(:shared_resource_id AS uuid)
            """
        ),
        {"shared_resource_id": created.data.sharedResourceId},
    ).mappings().one()

    assert str(persisted["organization_id"]) == organization_id
    assert persisted["resource_code"] == created.data.resourceCode
    assert persisted["name"] == "Community Warehouse"
    assert persisted["resource_type"] == "warehouse"
    assert persisted["status"] == "draft"
    assert float(persisted["capacity_value"]) == 50.0
    assert persisted["capacity_unit"] == "ton"
    assert persisted["description"] == "Shared storage for multiple scopes"


@pytest.mark.postgres_integration
def test_shared_resource_allocation_and_release_persist_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_shared_resource_service(monkeypatch, postgres_db_session)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)
    _seed_project_scope(postgres_db_session, project_scope_id, organization_id)

    created = shared_resource_service.create_shared_resource(
        CreateSharedResourceRequest(
            organizationId=organization_id,
            name="Community Vehicle Pool",
            resourceType="vehicle",
            capacityValue=8,
            capacityUnit="slot",
            description="Shared vehicles",
            meta=Meta(
                correlationId="corr-pg-shared-resource-alloc-create",
                idempotencyKey="idem-pg-shared-resource-alloc-create",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        )
    )

    allocated = shared_resource_service.allocate_shared_resource(
        created.data.sharedResourceId,
        AllocateSharedResourceRequest(
            projectScopeId=project_scope_id,
            allocationBasis="manual",
            allocatedCapacity=3,
            meta=Meta(
                correlationId="corr-pg-shared-resource-allocate",
                idempotencyKey="idem-pg-shared-resource-allocate",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    released = shared_resource_service.release_shared_resource_allocation(
        created.data.sharedResourceId,
        allocated.data.allocationId,
        ReleaseSharedResourceAllocationRequest(
            releasedCapacity=3,
            meta=Meta(
                correlationId="corr-pg-shared-resource-release",
                idempotencyKey="idem-pg-shared-resource-release",
                actorId="admin-pg-1",
                actorRole="admin",
            ),
        ),
    )

    fetched_resource = shared_resource_store.fetch_shared_resource(created.data.sharedResourceId)

    assert allocated.data.allocatedCapacity == 3.0
    assert allocated.data.status == "active"
    assert released.data.releasedCapacity == 3.0
    assert released.data.status == "released"
    assert fetched_resource is not None