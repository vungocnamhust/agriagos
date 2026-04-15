"""Project scope store operations."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "fetch_project_scope",
    "list_project_scopes",
    "project_scope_code_exists",
    "project_scope_exists",
    "upsert_project_scope",
]


def project_scope_exists(project_scope_id: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM project_scopes WHERE project_scope_id = :project_scope_id"),
            {"project_scope_id": project_scope_id},
        ).first()
    return row is not None


def project_scope_code_exists(project_scope_code: str) -> bool:
    if not _db.is_enabled():
        return False

    with _db.read_session() as session:
        row = session.execute(
            text("SELECT 1 FROM project_scopes WHERE project_scope_code = :project_scope_code"),
            {"project_scope_code": project_scope_code},
        ).first()
    return row is not None


def upsert_project_scope(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
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
                    description,
                    parent_project_scope_id,
                    metadata_json,
                    updated_at
                ) VALUES (
                    :project_scope_id,
                    :organization_id,
                    :project_scope_code,
                    :name,
                    :project_scope_type,
                    :status,
                    :season_year,
                    :owner_actor_id,
                    :description,
                    :parent_project_scope_id,
                    CAST(:metadata_json AS jsonb),
                    now()
                )
                ON CONFLICT (project_scope_id) DO UPDATE SET
                    organization_id = EXCLUDED.organization_id,
                    name = EXCLUDED.name,
                    project_scope_type = EXCLUDED.project_scope_type,
                    status = EXCLUDED.status,
                    season_year = EXCLUDED.season_year,
                    owner_actor_id = EXCLUDED.owner_actor_id,
                    description = EXCLUDED.description,
                    parent_project_scope_id = EXCLUDED.parent_project_scope_id,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "project_scope_id": record["projectScopeId"],
                "organization_id": record["organizationId"],
                "project_scope_code": record["projectScopeCode"],
                "name": record["name"],
                "project_scope_type": record["projectScopeType"],
                "status": record["status"],
                "season_year": record.get("seasonYear"),
                "owner_actor_id": record.get("ownerActorId"),
                "description": record.get("description"),
                "parent_project_scope_id": record.get("parentProjectScopeId"),
                "metadata_json": json.dumps(record.get("metadata") or {}),
            },
        )
        if should_commit:
            session.commit()


def list_project_scopes() -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT project_scope_id, organization_id, project_scope_code, name, project_scope_type, status, season_year, owner_actor_id, created_at
                FROM project_scopes
                ORDER BY created_at DESC
                """
            )
        ).mappings().all()

    return [
        {
            "projectScopeId": str(row["project_scope_id"]),
            "organizationId": str(row["organization_id"]),
            "projectScopeCode": row["project_scope_code"],
            "name": row["name"],
            "projectScopeType": row["project_scope_type"],
            "status": row["status"],
            "seasonYear": row["season_year"],
            "ownerActorId": row["owner_actor_id"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]


def fetch_project_scope(project_scope_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    project_scope_id,
                    organization_id,
                    project_scope_code,
                    name,
                    project_scope_type,
                    status,
                    season_year,
                    owner_actor_id,
                    description,
                    parent_project_scope_id,
                    metadata_json,
                    created_at,
                    updated_at
                FROM project_scopes
                WHERE project_scope_id = :project_scope_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "projectScopeId": str(row["project_scope_id"]),
        "organizationId": str(row["organization_id"]),
        "projectScopeCode": row["project_scope_code"],
        "name": row["name"],
        "projectScopeType": row["project_scope_type"],
        "status": row["status"],
        "seasonYear": row["season_year"],
        "ownerActorId": row["owner_actor_id"],
        "description": row["description"],
        "parentProjectScopeId": str(row["parent_project_scope_id"]) if row["parent_project_scope_id"] else None,
        "metadata": dict(row["metadata_json"] or {}),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "updatedAt": row["updated_at"].isoformat() if row["updated_at"] else None,
    }