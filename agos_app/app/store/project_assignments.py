"""Project assignment store operations."""
from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.store import _db


def upsert_project_assignment(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO project_assignments (
                    project_assignment_id,
                    project_scope_id,
                    target_type,
                    target_id,
                    is_primary,
                    attribution_weight,
                    ended_at,
                    ended_reason,
                    metadata_json,
                    updated_at
                ) VALUES (
                    :project_assignment_id,
                    :project_scope_id,
                    :target_type,
                    :target_id,
                    :is_primary,
                    :attribution_weight,
                    :ended_at,
                    :ended_reason,
                    CAST(:metadata_json AS jsonb),
                    now()
                )
                ON CONFLICT (project_assignment_id) DO UPDATE SET
                    is_primary = EXCLUDED.is_primary,
                    attribution_weight = EXCLUDED.attribution_weight,
                    ended_at = EXCLUDED.ended_at,
                    ended_reason = EXCLUDED.ended_reason,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "project_assignment_id": record["projectAssignmentId"],
                "project_scope_id": record["projectScopeId"],
                "target_type": record["targetType"],
                "target_id": record["targetId"],
                "is_primary": record.get("isPrimary", False),
                "attribution_weight": record.get("attributionWeight"),
                "ended_at": record.get("endedAt"),
                "ended_reason": record.get("endedReason"),
                "metadata_json": json.dumps(record.get("metadata") or {}),
            },
        )
        if should_commit:
            session.commit()


def list_project_assignments(project_scope_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    project_assignment_id,
                    project_scope_id,
                    target_type,
                    target_id,
                    is_primary,
                    attribution_weight,
                    created_at,
                    ended_at,
                    ended_reason,
                    metadata_json
                FROM project_assignments
                WHERE project_scope_id = :project_scope_id
                ORDER BY created_at, project_assignment_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().all()

    return [_map_project_assignment_row(row) for row in rows]


def fetch_project_assignment(project_assignment_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    project_assignment_id,
                    project_scope_id,
                    target_type,
                    target_id,
                    is_primary,
                    attribution_weight,
                    created_at,
                    ended_at,
                    ended_reason,
                    metadata_json
                FROM project_assignments
                WHERE project_assignment_id = :project_assignment_id
                """
            ),
            {"project_assignment_id": project_assignment_id},
        ).mappings().first()

    if row is None:
        return None
    return _map_project_assignment_row(row)


def _map_project_assignment_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "projectAssignmentId": str(row["project_assignment_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "targetType": row["target_type"],
        "targetId": str(row["target_id"]),
        "isPrimary": bool(row["is_primary"]),
        "attributionWeight": _db.to_float(row["attribution_weight"]) if row["attribution_weight"] is not None else None,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        "endedAt": row["ended_at"].isoformat() if row["ended_at"] else None,
        "endedReason": row["ended_reason"],
        "metadata": dict(row["metadata_json"] or {}),
    }