"""Lot/batch store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, _to_float, is_enabled

__all__ = ["upsert_lot", "fetch_lot"]


def upsert_lot(record: dict[str, Any]) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO lots (
                    lot_id,
                    lot_code,
                    product_sku_id,
                    source_type,
                    source_ref_id,
                    harvest_or_production_date,
                    actual_qty,
                    available_qty,
                    reserved_qty,
                    released_qty,
                    quality_note,
                    status,
                    tenant_id,
                    updated_at
                ) VALUES (
                    :lot_id,
                    :lot_code,
                    :product_sku_id,
                    :source_type,
                    :source_ref_id,
                    :harvest_or_production_date,
                    :actual_qty,
                    :available_qty,
                    :reserved_qty,
                    :released_qty,
                    :quality_note,
                    :status,
                    :tenant_id,
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
                    quality_note = EXCLUDED.quality_note,
                    status = EXCLUDED.status,
                    updated_at = now()
                """
            ),
            {
                "lot_id": record["lotId"],
                "lot_code": record["lotCode"],
                "product_sku_id": record["productSkuId"],
                "source_type": record["sourceType"],
                "source_ref_id": record["sourceRefId"],
                "harvest_or_production_date": record["harvestOrProductionDate"],
                "actual_qty": record["actualQty"],
                "available_qty": record.get("availableQty", 0),
                "reserved_qty": record.get("reservedQty", 0),
                "released_qty": record.get("releasedQty", 0),
                "quality_note": record.get("qualityNote"),
                "status": record["status"],
                "tenant_id": record.get("tenantId", "default"),
            },
        )
        session.commit()


def fetch_lot(lot_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        row = session.execute(
            text(
                """
                SELECT
                    lot_id,
                    lot_code,
                    product_sku_id,
                    source_type,
                    source_ref_id,
                    harvest_or_production_date,
                    actual_qty,
                    available_qty,
                    reserved_qty,
                    released_qty,
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
        "lotCode": row["lot_code"],
        "productSkuId": str(row["product_sku_id"]),
        "sourceType": row["source_type"],
        "sourceRefId": row["source_ref_id"],
        "harvestOrProductionDate": (
            row["harvest_or_production_date"].isoformat()
            if row["harvest_or_production_date"] else None
        ),
        "actualQty": _to_float(row["actual_qty"]),
        "availableQty": _to_float(row["available_qty"]),
        "reservedQty": _to_float(row["reserved_qty"]),
        "releasedQty": _to_float(row["released_qty"]),
        "qualityNote": row["quality_note"],
        "status": row["status"],
    }
