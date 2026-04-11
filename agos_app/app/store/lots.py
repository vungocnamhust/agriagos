"""Lot/batch store operations."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "append_lot_evidence",
    "create_lot_evidence",
    "create_qc_review",
    "create_qc_review_with_lot_status",
    "fetch_lot",
    "list_lot_evidence",
    "list_qc_reviews",
    "upsert_lot",
]
def append_lot_evidence(lot_id: str, attachments: list[str], actor_id: str | None = None) -> None:
    if not _db.is_enabled() or not attachments:
        return

    for attachment in attachments:
        create_lot_evidence(
            lot_id,
            {
                "tenantId": "default",
                "evidenceType": "document",
                "objectStorageKey": attachment,
                "actorId": actor_id,
                "status": "active",
            },
        )


def create_lot_evidence(lot_id: str, evidence: dict[str, Any]) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    evidence_id = str(uuid.uuid4())
    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                INSERT INTO lot_evidence (
                    lot_evidence_id,
                    tenant_id,
                    lot_id,
                    evidence_type,
                    object_storage_key,
                    text_value,
                    actor_id,
                    status
                ) VALUES (
                    :lot_evidence_id,
                    :tenant_id,
                    :lot_id,
                    :evidence_type,
                    :object_storage_key,
                    :text_value,
                    :actor_id,
                    :status
                )
                RETURNING lot_evidence_id, lot_id, evidence_type, object_storage_key, text_value, captured_at, actor_id, status
                """
            ),
            {
                "lot_evidence_id": evidence_id,
                "tenant_id": evidence.get("tenantId", "default"),
                "lot_id": lot_id,
                "evidence_type": evidence["evidenceType"],
                "object_storage_key": evidence.get("objectStorageKey"),
                "text_value": evidence.get("textValue"),
                "actor_id": evidence.get("actorId"),
                "status": evidence.get("status", "active"),
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None

    return {
        "lotEvidenceId": str(row["lot_evidence_id"]),
        "lotId": str(row["lot_id"]),
        "evidenceType": row["evidence_type"],
        "objectStorageKey": row["object_storage_key"],
        "textValue": row["text_value"],
        "capturedAt": row["captured_at"].isoformat(),
        "actorId": row["actor_id"],
        "status": row["status"],
    }


def list_lot_evidence(lot_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    lot_evidence_id,
                    lot_id,
                    evidence_type,
                    object_storage_key,
                    text_value,
                    captured_at,
                    actor_id,
                    status
                FROM lot_evidence
                WHERE lot_id = :lot_id
                ORDER BY captured_at DESC, created_at DESC
                """
            ),
            {"lot_id": lot_id},
        ).mappings().all()

    return [
        {
            "lotEvidenceId": str(row["lot_evidence_id"]),
            "lotId": str(row["lot_id"]),
            "evidenceType": row["evidence_type"],
            "objectStorageKey": row["object_storage_key"],
            "textValue": row["text_value"],
            "capturedAt": row["captured_at"].isoformat(),
            "actorId": row["actor_id"],
            "status": row["status"],
        }
        for row in rows
    ]


def create_qc_review(lot_id: str, review: dict[str, Any]) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    review_id = str(uuid.uuid4())
    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                INSERT INTO qc_reviews (
                    qc_review_id,
                    tenant_id,
                    lot_id,
                    checklist_version,
                    result,
                    reviewer_id,
                    notes
                ) VALUES (
                    :qc_review_id,
                    :tenant_id,
                    :lot_id,
                    :checklist_version,
                    :result,
                    :reviewer_id,
                    :notes
                )
                RETURNING qc_review_id, lot_id, checklist_version, result, reviewer_id, reviewed_at, notes
                """
            ),
            {
                "qc_review_id": review_id,
                "tenant_id": review.get("tenantId", "default"),
                "lot_id": lot_id,
                "checklist_version": review["checklistVersion"],
                "result": review["result"],
                "reviewer_id": review.get("reviewerId"),
                "notes": review.get("notes"),
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None

    return {
        "qcReviewId": str(row["qc_review_id"]),
        "lotId": str(row["lot_id"]),
        "checklistVersion": row["checklist_version"],
        "result": row["result"],
        "reviewerId": row["reviewer_id"],
        "reviewedAt": row["reviewed_at"].isoformat(),
        "notes": row["notes"],
    }


def create_qc_review_with_lot_status(
    lot_id: str,
    next_status: str,
    review: dict[str, Any],
) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    review_id = str(uuid.uuid4())
    with _db.write_session() as (session, should_commit):
        session.execute(
            text("SELECT lot_id FROM lots WHERE lot_id = :lot_id FOR UPDATE"),
            {"lot_id": lot_id},
        ).first()
        session.execute(
            text(
                """
                UPDATE lots
                SET status = :status, updated_at = now()
                WHERE lot_id = :lot_id
                """
            ),
            {"lot_id": lot_id, "status": next_status},
        )
        row = session.execute(
            text(
                """
                INSERT INTO qc_reviews (
                    qc_review_id,
                    tenant_id,
                    lot_id,
                    checklist_version,
                    result,
                    reviewer_id,
                    notes
                ) VALUES (
                    :qc_review_id,
                    :tenant_id,
                    :lot_id,
                    :checklist_version,
                    :result,
                    :reviewer_id,
                    :notes
                )
                RETURNING qc_review_id, lot_id, checklist_version, result, reviewer_id, reviewed_at, notes
                """
            ),
            {
                "qc_review_id": review_id,
                "tenant_id": review.get("tenantId", "default"),
                "lot_id": lot_id,
                "checklist_version": review["checklistVersion"],
                "result": review["result"],
                "reviewer_id": review.get("reviewerId"),
                "notes": review.get("notes"),
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None

    return {
        "qcReviewId": str(row["qc_review_id"]),
        "lotId": str(row["lot_id"]),
        "checklistVersion": row["checklist_version"],
        "result": row["result"],
        "reviewerId": row["reviewer_id"],
        "reviewedAt": row["reviewed_at"].isoformat(),
        "notes": row["notes"],
    }


def list_qc_reviews(lot_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    qc_review_id,
                    lot_id,
                    checklist_version,
                    result,
                    reviewer_id,
                    reviewed_at,
                    notes
                FROM qc_reviews
                WHERE lot_id = :lot_id
                ORDER BY reviewed_at DESC, created_at DESC
                """
            ),
            {"lot_id": lot_id},
        ).mappings().all()

    return [
        {
            "qcReviewId": str(row["qc_review_id"]),
            "lotId": str(row["lot_id"]),
            "checklistVersion": row["checklist_version"],
            "result": row["result"],
            "reviewerId": row["reviewer_id"],
            "reviewedAt": row["reviewed_at"].isoformat(),
            "notes": row["notes"],
        }
        for row in rows
    ]


def upsert_lot(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO lots (
                    lot_id,
                    tenant_id,
                    lot_code,
                    product_sku_id,
                    source_type,
                    source_ref_id,
                    harvest_or_production_date,
                    actual_qty,
                    available_qty,
                    reserved_qty,
                    released_qty,
                    unit,
                    quality_note,
                    status,
                    updated_at
                ) VALUES (
                    :lot_id,
                    :tenant_id,
                    :lot_code,
                    :product_sku_id,
                    :source_type,
                    :source_ref_id,
                    :harvest_or_production_date,
                    :actual_qty,
                    :available_qty,
                    :reserved_qty,
                    :released_qty,
                    :unit,
                    :quality_note,
                    :status,
                    now()
                )
                ON CONFLICT (lot_id) DO UPDATE SET
                    lot_code = EXCLUDED.lot_code,
                    product_sku_id = EXCLUDED.product_sku_id,
                    source_type = EXCLUDED.source_type,
                    source_ref_id = EXCLUDED.source_ref_id,
                    harvest_or_production_date = EXCLUDED.harvest_or_production_date,
                    actual_qty = EXCLUDED.actual_qty,
                    available_qty = EXCLUDED.available_qty,
                    reserved_qty = EXCLUDED.reserved_qty,
                    released_qty = EXCLUDED.released_qty,
                    unit = EXCLUDED.unit,
                    quality_note = EXCLUDED.quality_note,
                    status = EXCLUDED.status,
                    updated_at = now()
                """
            ),
            {
                "lot_id": record["lotId"],
                "tenant_id": record.get("tenantId", "default"),
                "lot_code": record["lotCode"],
                "product_sku_id": record["productSkuId"],
                "source_type": record["sourceType"],
                "source_ref_id": record["sourceRefId"],
                "harvest_or_production_date": record["harvestOrProductionDate"],
                "actual_qty": record["actualQty"],
                "available_qty": record.get("availableQty", 0),
                "reserved_qty": record.get("reservedQty", 0),
                "released_qty": record.get("releasedQty", 0),
                "unit": record.get("unit", "kg"),
                "quality_note": record.get("qualityNote"),
                "status": record["status"],
            },
        )
        if should_commit:
            session.commit()


def fetch_lot(lot_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    lot_id,
                    tenant_id,
                    lot_code,
                    product_sku_id,
                    source_type,
                    source_ref_id,
                    harvest_or_production_date,
                    actual_qty,
                    available_qty,
                    reserved_qty,
                    released_qty,
                    unit,
                    quality_note,
                    status
                FROM lots
                WHERE lot_id = :lot_id
                """
            ),
            {"lot_id": lot_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "lotId": str(row["lot_id"]),
        "tenantId": row["tenant_id"],
        "lotCode": row["lot_code"],
        "productSkuId": str(row["product_sku_id"]),
        "sourceType": row["source_type"],
        "sourceRefId": row["source_ref_id"],
        "harvestOrProductionDate": (
            row["harvest_or_production_date"].isoformat()
            if row["harvest_or_production_date"] else None
        ),
        "actualQty": _db.to_float(row["actual_qty"]),
        "availableQty": _db.to_float(row["available_qty"]),
        "reservedQty": _db.to_float(row["reserved_qty"]),
        "releasedQty": _db.to_float(row["released_qty"]),
        "unit": row["unit"],
        "qualityNote": row["quality_note"],
        "status": row["status"],
    }
