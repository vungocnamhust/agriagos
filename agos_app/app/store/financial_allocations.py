"""Financial allocation store operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.store import _db


def upsert_financial_allocation(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO financial_allocations (
                    financial_allocation_id,
                    project_scope_id,
                    organization_id,
                    source_record_type,
                    source_record_id,
                    allocation_basis,
                    allocation_weight,
                    allocated_amount,
                    currency,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :financial_allocation_id,
                    :project_scope_id,
                    :organization_id,
                    :source_record_type,
                    :source_record_id,
                    :allocation_basis,
                    :allocation_weight,
                    :allocated_amount,
                    :currency,
                    CAST(:metadata_json AS jsonb),
                    :created_at,
                    now()
                )
                ON CONFLICT (financial_allocation_id) DO UPDATE SET
                    allocation_weight = EXCLUDED.allocation_weight,
                    allocated_amount = EXCLUDED.allocated_amount,
                    currency = EXCLUDED.currency,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "financial_allocation_id": record["financialAllocationId"],
                "project_scope_id": record["projectScopeId"],
                "organization_id": record["organizationId"],
                "source_record_type": record["sourceRecordType"],
                "source_record_id": record["sourceRecordId"],
                "allocation_basis": record["allocationBasis"],
                "allocation_weight": record["allocationWeight"],
                "allocated_amount": record["allocatedAmount"],
                "currency": record["currency"],
                "metadata_json": json.dumps(record.get("metadata") or {}),
                "created_at": record.get("createdAt"),
            },
        )
        if should_commit:
            session.commit()


def acquire_financial_allocation_source_lock(source_record_type: str, source_record_id: str) -> None:
    if not _db.is_enabled():
        return

    with _db.read_session() as session:
        session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"),
            {"lock_key": f"financial-allocation:{source_record_type}:{source_record_id}"},
        )


def list_financial_allocations(project_scope_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    financial_allocation_id,
                    project_scope_id,
                    organization_id,
                    source_record_type,
                    source_record_id,
                    allocation_basis,
                    allocation_weight,
                    allocated_amount,
                    currency,
                    metadata_json,
                    created_at
                FROM financial_allocations
                WHERE project_scope_id = :project_scope_id
                ORDER BY created_at DESC, financial_allocation_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().all()
    return [_map_financial_allocation_row(row) for row in rows]


def fetch_financial_allocation_by_source(project_scope_id: str, source_record_type: str, source_record_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    financial_allocation_id,
                    project_scope_id,
                    organization_id,
                    source_record_type,
                    source_record_id,
                    allocation_basis,
                    allocation_weight,
                    allocated_amount,
                    currency,
                    metadata_json,
                    created_at
                FROM financial_allocations
                WHERE project_scope_id = :project_scope_id
                  AND source_record_type = :source_record_type
                  AND source_record_id = :source_record_id
                """
            ),
            {
                "project_scope_id": project_scope_id,
                "source_record_type": source_record_type,
                "source_record_id": source_record_id,
            },
        ).mappings().first()
    if row is None:
        return None
    return _map_financial_allocation_row(row)


def fetch_financial_allocation_by_source_record(source_record_type: str, source_record_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    financial_allocation_id,
                    project_scope_id,
                    organization_id,
                    source_record_type,
                    source_record_id,
                    allocation_basis,
                    allocation_weight,
                    allocated_amount,
                    currency,
                    metadata_json,
                    created_at
                FROM financial_allocations
                WHERE source_record_type = :source_record_type
                  AND source_record_id = :source_record_id
                """
            ),
            {
                "source_record_type": source_record_type,
                "source_record_id": source_record_id,
            },
        ).mappings().first()
    if row is None:
        return None
    return _map_financial_allocation_row(row)


def list_financial_allocations_by_source_record(source_record_type: str, source_record_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    financial_allocation_id,
                    project_scope_id,
                    organization_id,
                    source_record_type,
                    source_record_id,
                    allocation_basis,
                    allocation_weight,
                    allocated_amount,
                    currency,
                    metadata_json,
                    created_at
                FROM financial_allocations
                WHERE source_record_type = :source_record_type
                  AND source_record_id = :source_record_id
                ORDER BY created_at ASC, financial_allocation_id ASC
                """
            ),
            {
                "source_record_type": source_record_type,
                "source_record_id": source_record_id,
            },
        ).mappings().all()
    return [_map_financial_allocation_row(row) for row in rows]


def _map_financial_allocation_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    return {
        "financialAllocationId": str(row["financial_allocation_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "organizationId": str(row["organization_id"]),
        "sourceRecordType": row["source_record_type"],
        "sourceRecordId": str(row["source_record_id"]),
        "allocationBasis": row["allocation_basis"],
        "allocationWeight": _db.to_float(row["allocation_weight"]),
        "allocatedAmount": _db.to_float(row["allocated_amount"]),
        "currency": row["currency"],
        "metadata": dict(row["metadata_json"] or {}),
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }