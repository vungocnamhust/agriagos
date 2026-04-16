"""Actor identity and affiliation store operations."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "actor_code_exists",
    "actor_identity_exists",
    "fetch_actor_identity",
    "upsert_actor_identity",
    "upsert_actor_affiliation",
]


def actor_identity_exists(actor_id: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM actor_identities WHERE actor_id = :actor_id"),
            {"actor_id": actor_id},
        ).first()
    return row is not None


def actor_code_exists(actor_code: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM actor_identities WHERE actor_code = :actor_code"),
            {"actor_code": actor_code},
        ).first()
    return row is not None


def upsert_actor_identity(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO actor_identities (
                    actor_id,
                    tenant_id,
                    actor_code,
                    actor_type,
                    display_name,
                    status,
                    primary_phone,
                    primary_email,
                    external_mappings_json,
                    metadata_json,
                    updated_at
                ) VALUES (
                    :actor_id,
                    :tenant_id,
                    :actor_code,
                    :actor_type,
                    :display_name,
                    :status,
                    :primary_phone,
                    :primary_email,
                    CAST(:external_mappings_json AS jsonb),
                    CAST(:metadata_json AS jsonb),
                    now()
                )
                ON CONFLICT (actor_id) DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    actor_type = EXCLUDED.actor_type,
                    display_name = EXCLUDED.display_name,
                    status = EXCLUDED.status,
                    primary_phone = EXCLUDED.primary_phone,
                    primary_email = EXCLUDED.primary_email,
                    external_mappings_json = EXCLUDED.external_mappings_json,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "actor_id": record["actorId"],
                "tenant_id": record.get("tenantId", "default"),
                "actor_code": record["actorCode"],
                "actor_type": record["actorType"],
                "display_name": record["displayName"],
                "status": record["status"],
                "primary_phone": record.get("primaryPhone"),
                "primary_email": record.get("primaryEmail"),
                "external_mappings_json": json.dumps(record.get("externalMappingsJson") or {}),
                "metadata_json": json.dumps(record.get("metadata") or {}),
            },
        )
        if should_commit:
            session.commit()


def fetch_actor_identity(actor_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    actor_id,
                    tenant_id,
                    actor_code,
                    actor_type,
                    display_name,
                    status,
                    primary_phone,
                    primary_email,
                    external_mappings_json,
                    metadata_json,
                    created_at,
                    updated_at
                FROM actor_identities
                WHERE actor_id = :actor_id
                """
            ),
            {"actor_id": actor_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "actorId": str(row["actor_id"]),
        "tenantId": row["tenant_id"],
        "actorCode": row["actor_code"],
        "actorType": row["actor_type"],
        "displayName": row["display_name"],
        "status": row["status"],
        "primaryPhone": row["primary_phone"],
        "primaryEmail": row["primary_email"],
        "externalMappingsJson": dict(row["external_mappings_json"] or {}),
        "metadata": dict(row["metadata_json"] or {}),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


def upsert_actor_affiliation(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO actor_affiliations (
                    actor_affiliation_id,
                    actor_id,
                    organization_id,
                    project_scope_id,
                    affiliation_kind,
                    status,
                    effective_at,
                    ended_at,
                    confirmed_by,
                    confirmed_at,
                    metadata_json,
                    updated_at
                ) VALUES (
                    :actor_affiliation_id,
                    :actor_id,
                    :organization_id,
                    :project_scope_id,
                    :affiliation_kind,
                    :status,
                    CAST(:effective_at AS timestamptz),
                    CAST(:ended_at AS timestamptz),
                    :confirmed_by,
                    CAST(:confirmed_at AS timestamptz),
                    CAST(:metadata_json AS jsonb),
                    now()
                )
                ON CONFLICT (actor_affiliation_id) DO UPDATE SET
                    actor_id = EXCLUDED.actor_id,
                    organization_id = EXCLUDED.organization_id,
                    project_scope_id = EXCLUDED.project_scope_id,
                    affiliation_kind = EXCLUDED.affiliation_kind,
                    status = EXCLUDED.status,
                    effective_at = EXCLUDED.effective_at,
                    ended_at = EXCLUDED.ended_at,
                    confirmed_by = EXCLUDED.confirmed_by,
                    confirmed_at = EXCLUDED.confirmed_at,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "actor_affiliation_id": record["actorAffiliationId"],
                "actor_id": record["actorId"],
                "organization_id": record.get("organizationId"),
                "project_scope_id": record.get("projectScopeId"),
                "affiliation_kind": record["affiliationKind"],
                "status": record["status"],
                "effective_at": record["effectiveAt"],
                "ended_at": record.get("endedAt"),
                "confirmed_by": record.get("confirmedBy"),
                "confirmed_at": record.get("confirmedAt"),
                "metadata_json": json.dumps(record.get("metadata") or {}),
            },
        )
        if should_commit:
            session.commit()