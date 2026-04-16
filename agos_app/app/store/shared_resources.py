"""Shared resource store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "fetch_shared_resource",
    "list_shared_resources",
    "shared_resource_code_exists",
    "shared_resource_exists",
    "upsert_shared_resource",
]


def shared_resource_exists(shared_resource_id: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM shared_resources WHERE shared_resource_id = :shared_resource_id"),
            {"shared_resource_id": shared_resource_id},
        ).first()
    return row is not None


def shared_resource_code_exists(resource_code: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM shared_resources WHERE resource_code = :resource_code"),
            {"resource_code": resource_code},
        ).first()
    return row is not None


def upsert_shared_resource(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO shared_resources (
                    shared_resource_id,
                    organization_id,
                    resource_code,
                    name,
                    resource_type,
                    status,
                    capacity_value,
                    capacity_unit,
                    description,
                    updated_at
                ) VALUES (
                    :shared_resource_id,
                    :organization_id,
                    :resource_code,
                    :name,
                    :resource_type,
                    :status,
                    :capacity_value,
                    :capacity_unit,
                    :description,
                    now()
                )
                ON CONFLICT (shared_resource_id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    name = EXCLUDED.name,
                    resource_type = EXCLUDED.resource_type,
                    status = EXCLUDED.status,
                    capacity_value = EXCLUDED.capacity_value,
                    capacity_unit = EXCLUDED.capacity_unit,
                    description = EXCLUDED.description,
                    updated_at = now()
                """
            ),
            {
                "shared_resource_id": record["sharedResourceId"],
                "organization_id": record["organizationId"],
                "resource_code": record["resourceCode"],
                "name": record["name"],
                "resource_type": record["resourceType"],
                "status": record["status"],
                "capacity_value": record.get("capacityValue"),
                "capacity_unit": record.get("capacityUnit"),
                "description": record.get("description"),
            },
        )
        if should_commit:
            session.commit()


def list_shared_resources() -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    shared_resource_id,
                    organization_id,
                    resource_code,
                    name,
                    resource_type,
                    status,
                    capacity_value,
                    capacity_unit,
                    created_at
                FROM shared_resources
                ORDER BY created_at DESC, shared_resource_id
                """
            )
        ).mappings().all()

    return [
        {
            "sharedResourceId": str(row["shared_resource_id"]),
            "organizationId": str(row["organization_id"]),
            "resourceCode": row["resource_code"],
            "name": row["name"],
            "resourceType": row["resource_type"],
            "status": row["status"],
            "capacityValue": _db.to_float(row["capacity_value"]) if row["capacity_value"] is not None else None,
            "capacityUnit": row["capacity_unit"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def fetch_shared_resource(shared_resource_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    shared_resource_id,
                    organization_id,
                    resource_code,
                    name,
                    resource_type,
                    status,
                    capacity_value,
                    capacity_unit,
                    description,
                    created_at,
                    updated_at
                FROM shared_resources
                WHERE shared_resource_id = :shared_resource_id
                """
            ),
            {"shared_resource_id": shared_resource_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "sharedResourceId": str(row["shared_resource_id"]),
        "organizationId": str(row["organization_id"]),
        "resourceCode": row["resource_code"],
        "name": row["name"],
        "resourceType": row["resource_type"],
        "status": row["status"],
        "capacityValue": _db.to_float(row["capacity_value"]) if row["capacity_value"] is not None else None,
        "capacityUnit": row["capacity_unit"],
        "description": row["description"],
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }