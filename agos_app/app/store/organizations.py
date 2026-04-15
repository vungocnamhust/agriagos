"""Organization store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "fetch_organization",
    "list_organizations",
    "organization_code_exists",
    "organization_exists",
    "upsert_organization",
]


def organization_exists(organization_id: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM organizations WHERE organization_id = :organization_id"),
            {"organization_id": organization_id},
        ).first()
    return row is not None


def organization_code_exists(organization_code: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM organizations WHERE organization_code = :organization_code"),
            {"organization_code": organization_code},
        ).first()
    return row is not None


def upsert_organization(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO organizations (
                    organization_id,
                    tenant_id,
                    organization_code,
                    name,
                    organization_type,
                    status,
                    region,
                    locality_summary,
                    representative_name,
                    contact_phone,
                    contact_email,
                    short_description,
                    updated_at
                ) VALUES (
                    :organization_id,
                    :tenant_id,
                    :organization_code,
                    :name,
                    :organization_type,
                    :status,
                    :region,
                    :locality_summary,
                    :representative_name,
                    :contact_phone,
                    :contact_email,
                    :short_description,
                    now()
                )
                ON CONFLICT (organization_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    name = EXCLUDED.name,
                    organization_type = EXCLUDED.organization_type,
                    status = EXCLUDED.status,
                    region = EXCLUDED.region,
                    locality_summary = EXCLUDED.locality_summary,
                    representative_name = EXCLUDED.representative_name,
                    contact_phone = EXCLUDED.contact_phone,
                    contact_email = EXCLUDED.contact_email,
                    short_description = EXCLUDED.short_description,
                    updated_at = now()
                """
            ),
            {
                "organization_id": record["organizationId"],
                "tenant_id": record.get("tenantId", "default"),
                "organization_code": record["organizationCode"],
                "name": record["name"],
                "organization_type": record["organizationType"],
                "status": record["status"],
                "region": record.get("region"),
                "locality_summary": record.get("localitySummary"),
                "representative_name": record.get("representativeName"),
                "contact_phone": record.get("contactPhone"),
                "contact_email": record.get("contactEmail"),
                "short_description": record.get("shortDescription"),
            },
        )
        if should_commit:
            session.commit()


def list_organizations() -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT organization_id, organization_code, name, organization_type, status, region, created_at
                FROM organizations
                ORDER BY created_at DESC
                """
            )
        ).mappings().all()

    return [
        {
            "organizationId": str(row["organization_id"]),
            "organizationCode": row["organization_code"],
            "name": row["name"],
            "organizationType": row["organization_type"],
            "status": row["status"],
            "region": row["region"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def fetch_organization(organization_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    organization_id,
                    tenant_id,
                    organization_code,
                    name,
                    organization_type,
                    status,
                    region,
                    locality_summary,
                    representative_name,
                    contact_phone,
                    contact_email,
                    short_description,
                    created_at,
                    updated_at
                FROM organizations
                WHERE organization_id = :organization_id
                """
            ),
            {"organization_id": organization_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "organizationId": str(row["organization_id"]),
        "tenantId": row["tenant_id"],
        "organizationCode": row["organization_code"],
        "name": row["name"],
        "organizationType": row["organization_type"],
        "status": row["status"],
        "region": row["region"],
        "localitySummary": row["locality_summary"],
        "representativeName": row["representative_name"],
        "contactPhone": row["contact_phone"],
        "contactEmail": row["contact_email"],
        "shortDescription": row["short_description"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }