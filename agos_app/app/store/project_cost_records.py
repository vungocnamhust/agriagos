"""Project cost record store operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.store import _db


def upsert_project_cost_record(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO project_cost_records (
                    cost_record_id,
                    project_scope_id,
                    organization_id,
                    cost_type,
                    amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    attribution_policy,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :cost_record_id,
                    :project_scope_id,
                    :organization_id,
                    :cost_type,
                    :amount,
                    :currency,
                    :recognized_at,
                    :source_object_type,
                    :source_object_id,
                    :attribution_policy,
                    CAST(:metadata_json AS jsonb),
                    :created_at,
                    now()
                )
                ON CONFLICT (cost_record_id) DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    recognized_at = EXCLUDED.recognized_at,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "cost_record_id": record["costRecordId"],
                "project_scope_id": record["projectScopeId"],
                "organization_id": record["organizationId"],
                "cost_type": record["costType"],
                "amount": record["amount"],
                "currency": record["currency"],
                "recognized_at": record["recognizedAt"],
                "source_object_type": record["sourceObjectType"],
                "source_object_id": record["sourceObjectId"],
                "attribution_policy": record["attributionPolicy"],
                "metadata_json": json.dumps(record.get("metadata") or {}),
                "created_at": record.get("createdAt"),
            },
        )
        if should_commit:
            session.commit()


def list_project_cost_records(project_scope_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    cost_record_id,
                    project_scope_id,
                    organization_id,
                    cost_type,
                    amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    attribution_policy,
                    metadata_json,
                    created_at
                FROM project_cost_records
                WHERE project_scope_id = :project_scope_id
                ORDER BY recognized_at DESC, cost_record_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().all()
    return [_map_project_cost_record_row(row) for row in rows]


def fetch_project_cost_record(cost_record_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    cost_record_id,
                    project_scope_id,
                    organization_id,
                    cost_type,
                    amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    attribution_policy,
                    metadata_json,
                    created_at
                FROM project_cost_records
                WHERE cost_record_id = :cost_record_id
                """
            ),
            {"cost_record_id": cost_record_id},
        ).mappings().first()
    if row is None:
        return None
    return _map_project_cost_record_row(row)


def _map_project_cost_record_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        "costRecordId": str(row["cost_record_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "organizationId": str(row["organization_id"]),
        "costType": row["cost_type"],
        "amount": _db.to_float(row["amount"]),
        "currency": row["currency"],
        "recognizedAt": row["recognized_at"].isoformat() if row["recognized_at"] else None,
        "sourceObjectType": row["source_object_type"],
        "sourceObjectId": str(row["source_object_id"]),
        "attributionPolicy": row["attribution_policy"],
        "metadata": dict(row["metadata_json"] or {}),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }