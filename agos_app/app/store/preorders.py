"""Preorder store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, _to_float, is_enabled

__all__ = [
    "upsert_preorder",
    "fetch_preorder",
    "increment_delivered_qty_atomic",
]


def upsert_preorder(record: dict[str, Any]) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO preorders (
                    preorder_id,
                    preorder_code,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date,
                    tenant_id,
                    updated_at
                ) VALUES (
                    :preorder_id,
                    :preorder_code,
                    :customer_id,
                    :product_sku_id,
                    :committed_qty,
                    :allocated_qty,
                    :delivered_qty,
                    :remaining_qty,
                    :delivery_cadence,
                    :deposit_amount,
                    :notes,
                    :status,
                    COALESCE(CAST(:start_date AS date), CURRENT_DATE),
                    :tenant_id,
                    now()
                )
                ON CONFLICT (preorder_id) DO UPDATE SET
                    committed_qty = EXCLUDED.committed_qty,
                    allocated_qty = EXCLUDED.allocated_qty,
                    delivered_qty = EXCLUDED.delivered_qty,
                    remaining_qty = EXCLUDED.remaining_qty,
                    delivery_cadence = EXCLUDED.delivery_cadence,
                    deposit_amount = EXCLUDED.deposit_amount,
                    notes = EXCLUDED.notes,
                    status = EXCLUDED.status,
                    updated_at = now()
                """
            ),
            {
                "preorder_id": record["preorderId"],
                "preorder_code": record["preorderCode"],
                "customer_id": record["customerId"],
                "product_sku_id": record["productSkuId"],
                "committed_qty": record["committedQty"],
                "allocated_qty": record["allocatedQty"],
                "delivered_qty": record["deliveredQty"],
                "remaining_qty": record["remainingQty"],
                "delivery_cadence": record.get("deliveryCadence"),
                "deposit_amount": record.get("depositAmount"),
                "notes": record.get("notes"),
                "status": record["status"],
                "start_date": record.get("startDate"),
                "tenant_id": record.get("tenantId", "default"),
            },
        )
        session.commit()


def fetch_preorder(preorder_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        row = session.execute(
            text(
                """
                SELECT
                    preorder_id,
                    tenant_id,
                    preorder_code,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date
                FROM preorders
                WHERE preorder_id = :preorder_id
                """
            ),
            {"preorder_id": preorder_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "preorderId": str(row["preorder_id"]),
        "tenantId": row["tenant_id"],
        "preorderCode": row["preorder_code"],
        "customerId": str(row["customer_id"]),
        "productSkuId": str(row["product_sku_id"]),
        "committedQty": _to_float(row["committed_qty"]),
        "allocatedQty": _to_float(row["allocated_qty"]),
        "deliveredQty": _to_float(row["delivered_qty"]),
        "remainingQty": _to_float(row["remaining_qty"]),
        "deliveryCadence": row["delivery_cadence"],
        "depositAmount": _to_float(row["deposit_amount"]) if row["deposit_amount"] is not None else None,
        "notes": row["notes"],
        "status": row["status"],
        "startDate": row["start_date"].isoformat() if row["start_date"] else None,
    }


def increment_delivered_qty_atomic(preorder_id: str, qty_increment: float) -> dict[str, Any] | None:
    """Atomically increment deliveredQty and auto-complete preorder when fully delivered.

    This is the single SSoT path for updating preorder delivered quantity.
    Do NOT update preorder quantities directly from orders.py — always use this function.
    """
    if not is_enabled():
        return None

    with SessionLocal() as session:
        session.execute(
            text(
                """
                UPDATE preorders
                SET
                    delivered_qty = delivered_qty + :qty_increment,
                    remaining_qty = GREATEST(0, committed_qty - (delivered_qty + :qty_increment)),
                    status = CASE
                        WHEN committed_qty <= (delivered_qty + :qty_increment) THEN 'completed'
                        ELSE status
                    END,
                    updated_at = now()
                WHERE preorder_id = :preorder_id
                """
            ),
            {
                "preorder_id": preorder_id,
                "qty_increment": qty_increment,
            },
        )
        session.commit()

    return fetch_preorder(preorder_id)
