from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


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
            "name": "External Mapping Org",
        },
    )


@pytest.mark.postgres_integration
def test_external_mapping_can_persist_organization_id(postgres_db_session: Session) -> None:
    organization_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)

    external_mapping_id = postgres_db_session.execute(
        text(
            """
            INSERT INTO external_mappings (
                tenant_id,
                organization_id,
                external_system,
                external_object_type,
                external_object_id,
                internal_object_type,
                internal_object_id,
                sync_status
            ) VALUES (
                'default',
                :organization_id,
                'crm',
                'contact',
                :external_object_id,
                'customer',
                :internal_object_id,
                'pending'
            )
            RETURNING external_mapping_id
            """
        ),
        {
            "organization_id": organization_id,
            "external_object_id": f"crm-contact-{uuid.uuid4().hex[:8]}",
            "internal_object_id": str(uuid.uuid4()),
        },
    ).scalar_one()

    row = postgres_db_session.execute(
        text(
            """
            SELECT organization_id, external_system, internal_object_type, sync_status
            FROM external_mappings
            WHERE external_mapping_id = CAST(:external_mapping_id AS uuid)
            """
        ),
        {"external_mapping_id": external_mapping_id},
    ).mappings().one()

    assert str(row["organization_id"]) == organization_id
    assert row["external_system"] == "crm"
    assert row["internal_object_type"] == "customer"
    assert row["sync_status"] == "pending"


@pytest.mark.postgres_integration
def test_external_mapping_rejects_unknown_organization_id(postgres_db_session: Session) -> None:
    with pytest.raises(IntegrityError):
        postgres_db_session.execute(
            text(
                """
                INSERT INTO external_mappings (
                    tenant_id,
                    organization_id,
                    external_system,
                    external_object_type,
                    external_object_id,
                    internal_object_type,
                    internal_object_id,
                    sync_status
                ) VALUES (
                    'default',
                    CAST(:organization_id AS uuid),
                    'crm',
                    'contact',
                    :external_object_id,
                    'customer',
                    :internal_object_id,
                    'pending'
                )
                """
            ),
            {
                "organization_id": str(uuid.uuid4()),
                "external_object_id": f"crm-contact-{uuid.uuid4().hex[:8]}",
                "internal_object_id": str(uuid.uuid4()),
            },
        )
        postgres_db_session.flush()


@pytest.mark.postgres_integration
def test_external_mapping_accepts_null_organization_id(postgres_db_session: Session) -> None:
    external_mapping_id = postgres_db_session.execute(
        text(
            """
            INSERT INTO external_mappings (
                tenant_id,
                organization_id,
                external_system,
                external_object_type,
                external_object_id,
                internal_object_type,
                internal_object_id,
                sync_status
            ) VALUES (
                'default',
                NULL,
                'crm',
                'contact',
                :external_object_id,
                'customer',
                :internal_object_id,
                'pending'
            )
            RETURNING external_mapping_id
            """
        ),
        {
            "external_object_id": f"crm-contact-{uuid.uuid4().hex[:8]}",
            "internal_object_id": str(uuid.uuid4()),
        },
    ).scalar_one()

    row = postgres_db_session.execute(
        text(
            """
            SELECT organization_id
            FROM external_mappings
            WHERE external_mapping_id = CAST(:external_mapping_id AS uuid)
            """
        ),
        {"external_mapping_id": external_mapping_id},
    ).mappings().one()

    assert row["organization_id"] is None