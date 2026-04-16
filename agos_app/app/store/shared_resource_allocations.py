"""Shared resource allocation store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store import _db


def upsert_shared_resource_allocation(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO shared_resource_allocations (
                    allocation_id,
                    shared_resource_id,
                    project_scope_id,
                    allocation_basis,
                    allocated_capacity,
                    released_capacity,
                    status,
                    effective_at,
                    released_at,
                    created_at,
                    updated_at
                ) VALUES (
                    :allocation_id,
                    :shared_resource_id,
                    :project_scope_id,
                    :allocation_basis,
                    :allocated_capacity,
                    :released_capacity,
                    :status,
                    :effective_at,
                    :released_at,
                    :created_at,
                    now()
                )
                ON CONFLICT (allocation_id) DO UPDATE SET
                    released_capacity = EXCLUDED.released_capacity,
                    status = EXCLUDED.status,
                    released_at = EXCLUDED.released_at,
                    updated_at = now()
                """
            ),
            {
                "allocation_id": record["allocationId"],
                "shared_resource_id": record["sharedResourceId"],
                "project_scope_id": record["projectScopeId"],
                "allocation_basis": record["allocationBasis"],
                "allocated_capacity": record["allocatedCapacity"],
                "released_capacity": record["releasedCapacity"],
                "status": record["status"],
                "effective_at": record["effectiveAt"],
                "released_at": record.get("releasedAt"),
                "created_at": record.get("createdAt"),
            },
        )
        if should_commit:
            session.commit()


def fetch_shared_resource_allocation(allocation_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    allocation_id,
                    shared_resource_id,
                    project_scope_id,
                    allocation_basis,
                    allocated_capacity,
                    released_capacity,
                    status,
                    effective_at,
                    released_at,
                    created_at,
                    updated_at
                FROM shared_resource_allocations
                WHERE allocation_id = :allocation_id
                """
            ),
            {"allocation_id": allocation_id},
        ).mappings().first()

    if row is None:
        return None
    return _map_shared_resource_allocation(row)


def list_shared_resource_allocations(shared_resource_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    allocation_id,
                    shared_resource_id,
                    project_scope_id,
                    allocation_basis,
                    allocated_capacity,
                    released_capacity,
                    status,
                    effective_at,
                    released_at,
                    created_at,
                    updated_at
                FROM shared_resource_allocations
                WHERE shared_resource_id = :shared_resource_id
                ORDER BY created_at ASC, allocation_id ASC
                """
            ),
            {"shared_resource_id": shared_resource_id},
        ).mappings().all()
    return [_map_shared_resource_allocation(row) for row in rows]


def get_active_shared_resource_allocated_capacity(shared_resource_id: str) -> float:
    if not _db.is_enabled():
        return 0.0

    with _db.read_session() as session:
        value = session.execute(
            text(
                """
                SELECT COALESCE(SUM(allocated_capacity - released_capacity), 0)
                FROM shared_resource_allocations
                WHERE shared_resource_id = :shared_resource_id
                  AND status = 'active'
                """
            ),
            {"shared_resource_id": shared_resource_id},
        ).scalar_one()
    return _db.to_float(value)


def _map_shared_resource_allocation(row: Any) -> dict[str, Any]:
    return {
        "allocationId": str(row["allocation_id"]),
        "sharedResourceId": str(row["shared_resource_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "allocationBasis": row["allocation_basis"],
        "allocatedCapacity": _db.to_float(row["allocated_capacity"]),
        "releasedCapacity": _db.to_float(row["released_capacity"]),
        "status": row["status"],
        "effectiveAt": row["effective_at"].isoformat() if row["effective_at"] else None,
        "releasedAt": row["released_at"].isoformat() if row["released_at"] else None,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }