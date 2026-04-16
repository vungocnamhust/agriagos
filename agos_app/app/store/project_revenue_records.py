"""Project revenue record store operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.store import _db


def upsert_project_revenue_record(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO project_revenue_records (
                    revenue_record_id,
                    project_scope_id,
                    organization_id,
                    customer_id,
                    revenue_type,
                    gross_amount,
                    net_amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :revenue_record_id,
                    :project_scope_id,
                    :organization_id,
                    :customer_id,
                    :revenue_type,
                    :gross_amount,
                    :net_amount,
                    :currency,
                    :recognized_at,
                    :source_object_type,
                    :source_object_id,
                    CAST(:metadata_json AS jsonb),
                    :created_at,
                    now()
                )
                ON CONFLICT (revenue_record_id) DO UPDATE SET
                    gross_amount = EXCLUDED.gross_amount,
                    net_amount = EXCLUDED.net_amount,
                    currency = EXCLUDED.currency,
                    recognized_at = EXCLUDED.recognized_at,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "revenue_record_id": record["revenueRecordId"],
                "project_scope_id": record["projectScopeId"],
                "organization_id": record["organizationId"],
                "customer_id": record["customerId"],
                "revenue_type": record["revenueType"],
                "gross_amount": record["grossAmount"],
                "net_amount": record["netAmount"],
                "currency": record["currency"],
                "recognized_at": record["recognizedAt"],
                "source_object_type": record["sourceObjectType"],
                "source_object_id": record["sourceObjectId"],
                "metadata_json": json.dumps(record.get("metadata") or {}),
                "created_at": record.get("createdAt"),
            },
        )
        if should_commit:
            session.commit()


def list_project_revenue_records(project_scope_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    revenue_record_id,
                    project_scope_id,
                    organization_id,
                    customer_id,
                    revenue_type,
                    gross_amount,
                    net_amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    metadata_json,
                    created_at
                FROM project_revenue_records
                WHERE project_scope_id = :project_scope_id
                ORDER BY recognized_at DESC, revenue_record_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().all()
    return [_map_project_revenue_record_row(row) for row in rows]


def fetch_project_revenue_record_by_source(
    project_scope_id: str,
    source_object_type: str,
    source_object_id: str,
) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    revenue_record_id,
                    project_scope_id,
                    organization_id,
                    customer_id,
                    revenue_type,
                    gross_amount,
                    net_amount,
                    currency,
                    recognized_at,
                    source_object_type,
                    source_object_id,
                    metadata_json,
                    created_at
                FROM project_revenue_records
                WHERE project_scope_id = :project_scope_id
                  AND source_object_type = :source_object_type
                  AND source_object_id = :source_object_id
                """
            ),
            {
                "project_scope_id": project_scope_id,
                "source_object_type": source_object_type,
                "source_object_id": source_object_id,
            },
        ).mappings().first()
    if row is None:
        return None
    return _map_project_revenue_record_row(row)


def _map_project_revenue_record_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        "revenueRecordId": str(row["revenue_record_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "organizationId": str(row["organization_id"]),
        "customerId": str(row["customer_id"]),
        "revenueType": row["revenue_type"],
        "grossAmount": _db.to_float(row["gross_amount"]),
        "netAmount": _db.to_float(row["net_amount"]),
        "currency": row["currency"],
        "recognizedAt": row["recognized_at"].isoformat() if row["recognized_at"] else None,
        "sourceObjectType": row["source_object_type"],
        "sourceObjectId": str(row["source_object_id"]),
        "metadata": dict(row["metadata_json"] or {}),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }