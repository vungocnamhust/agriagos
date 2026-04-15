"""Preorder store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "upsert_preorder",
    "fetch_preorder",
    "append_preorder_adjustment",
    "increment_allocated_qty_atomic",
    "decrement_allocated_qty_atomic",
    "increment_delivered_qty_atomic",
]


def _float_value(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _preorder_record_from_row(row: Any) -> dict[str, Any]:
    return {
        "preorderId": str(row["preorder_id"]),
        "tenantId": row["tenant_id"],
        "preorderCode": row["preorder_code"],
        "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
        "customerId": str(row["customer_id"]),
        "productSkuId": str(row["product_sku_id"]),
        "committedQty": _float_value(row["committed_qty"]),
        "allocatedQty": _float_value(row["allocated_qty"]),
        "deliveredQty": _float_value(row["delivered_qty"]),
        "cancelledQty": _float_value(row["cancelled_qty"]),
        "remainingQty": _float_value(row["remaining_qty"]),
        "deliveryCadence": row["delivery_cadence"],
        "depositAmount": _float_value(row["deposit_amount"]) if row["deposit_amount"] is not None else None,
        "notes": row["notes"],
        "status": row["status"],
        "startDate": row["start_date"].isoformat() if row["start_date"] else None,
        "version": int(row["version"]) if row["version"] is not None else 1,
    }


def _preorder_adjustment_from_row(row: Any) -> dict[str, Any]:
    return {
        "oldCommittedQty": _float_value(row["old_committed_qty"]),
        "newCommittedQty": _float_value(row["new_committed_qty"]),
        "reason": row["reason"],
        "changedAt": row["changed_at"].isoformat() if row["changed_at"] else None,
        "actorId": row["actor_id"],
    }


def upsert_preorder(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO preorders (
                    preorder_id,
                    preorder_code,
                    organization_id,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    cancelled_qty,
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
                    :organization_id,
                    :customer_id,
                    :product_sku_id,
                    :committed_qty,
                    :allocated_qty,
                    :delivered_qty,
                    :cancelled_qty,
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
                    cancelled_qty = EXCLUDED.cancelled_qty,
                    remaining_qty = EXCLUDED.remaining_qty,
                    delivery_cadence = EXCLUDED.delivery_cadence,
                    deposit_amount = EXCLUDED.deposit_amount,
                    notes = EXCLUDED.notes,
                    status = EXCLUDED.status,
                    organization_id = EXCLUDED.organization_id,
                    version = preorders.version + 1,
                    updated_at = now()
                """
            ),
            {
                "preorder_id": record["preorderId"],
                "preorder_code": record["preorderCode"],
                "organization_id": record.get("organizationId"),
                "customer_id": record["customerId"],
                "product_sku_id": record["productSkuId"],
                "committed_qty": record["committedQty"],
                "allocated_qty": record["allocatedQty"],
                "delivered_qty": record["deliveredQty"],
                "cancelled_qty": record.get("cancelledQty", 0.0),
                "remaining_qty": record["remainingQty"],
                "delivery_cadence": record.get("deliveryCadence"),
                "deposit_amount": record.get("depositAmount"),
                "notes": record.get("notes"),
                "status": record["status"],
                "start_date": record.get("startDate"),
                "tenant_id": record.get("tenantId", "default"),
            },
        )
        if should_commit:
            session.commit()


def fetch_preorder(preorder_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    preorder_id,
                    tenant_id,
                    preorder_code,
                    organization_id,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    cancelled_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date,
                    version
                FROM preorders
                WHERE preorder_id = :preorder_id
                """
            ),
            {"preorder_id": preorder_id},
        ).mappings().first()

        adjustment_rows = session.execute(
            text(
                """
                SELECT
                    old_committed_qty,
                    new_committed_qty,
                    reason,
                    changed_at,
                    actor_id
                FROM preorder_adjustments
                WHERE preorder_id = :preorder_id
                ORDER BY changed_at DESC, adjustment_id DESC
                """
            ),
            {"preorder_id": preorder_id},
        ).mappings().all()

    if row is None:
        return None

    record = _preorder_record_from_row(row)
    record["adjustmentHistory"] = [_preorder_adjustment_from_row(item) for item in adjustment_rows]
    return record


def append_preorder_adjustment(preorder_id: str, adjustment: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO preorder_adjustments (
                    adjustment_id,
                    preorder_id,
                    old_committed_qty,
                    new_committed_qty,
                    reason,
                    actor_id,
                    changed_at
                ) VALUES (
                    gen_random_uuid(),
                    :preorder_id,
                    :old_committed_qty,
                    :new_committed_qty,
                    :reason,
                    :actor_id,
                    CAST(:changed_at AS timestamptz)
                )
                """
            ),
            {
                "preorder_id": preorder_id,
                "old_committed_qty": adjustment["oldCommittedQty"],
                "new_committed_qty": adjustment["newCommittedQty"],
                "reason": adjustment["reason"],
                "actor_id": adjustment.get("actorId"),
                "changed_at": adjustment["changedAt"],
            },
        )
        if should_commit:
            session.commit()


def increment_allocated_qty_atomic(preorder_id: str, qty_increment: float) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                UPDATE preorders
                SET
                    allocated_qty = allocated_qty + :qty_increment,
                    remaining_qty = GREATEST(0, committed_qty - (allocated_qty + :qty_increment) - delivered_qty - cancelled_qty),
                    version = version + 1,
                    updated_at = now()
                WHERE preorder_id = :preorder_id
                RETURNING
                    preorder_id,
                    tenant_id,
                    preorder_code,
                    organization_id,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    cancelled_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date,
                    version
                """
            ),
            {
                "preorder_id": preorder_id,
                "qty_increment": qty_increment,
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None
    record = _preorder_record_from_row(row)
    record["adjustmentHistory"] = []
    return record


def decrement_allocated_qty_atomic(preorder_id: str, qty_decrement: float) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                UPDATE preorders
                SET
                    allocated_qty = GREATEST(0, allocated_qty - :qty_decrement),
                    remaining_qty = GREATEST(0, committed_qty - GREATEST(0, allocated_qty - :qty_decrement) - delivered_qty - cancelled_qty),
                    version = version + 1,
                    updated_at = now()
                WHERE preorder_id = :preorder_id
                RETURNING
                    preorder_id,
                    tenant_id,
                    preorder_code,
                    organization_id,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    cancelled_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date,
                    version
                """
            ),
            {
                "preorder_id": preorder_id,
                "qty_decrement": qty_decrement,
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None
    record = _preorder_record_from_row(row)
    record["adjustmentHistory"] = []
    return record


def increment_delivered_qty_atomic(preorder_id: str, qty_increment: float) -> dict[str, Any] | None:
    """Atomically increment deliveredQty and auto-complete preorder when fully delivered.

    This is the single SSoT path for updating preorder delivered quantity.
    Do NOT update preorder quantities directly from orders.py — always use this function.
    """
    if not _db.is_enabled():
        return None

    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                UPDATE preorders
                SET
                    allocated_qty = GREATEST(0, allocated_qty - :qty_increment),
                    delivered_qty = delivered_qty + :qty_increment,
                    remaining_qty = GREATEST(
                        0,
                        committed_qty
                        - GREATEST(0, allocated_qty - :qty_increment)
                        - (delivered_qty + :qty_increment)
                        - cancelled_qty
                    ),
                    status = CASE
                        WHEN committed_qty <= (delivered_qty + :qty_increment + cancelled_qty) THEN 'completed'
                        ELSE status
                    END,
                    version = version + 1,
                    updated_at = now()
                WHERE preorder_id = :preorder_id
                RETURNING
                    preorder_id,
                    tenant_id,
                    preorder_code,
                    organization_id,
                    customer_id,
                    product_sku_id,
                    committed_qty,
                    allocated_qty,
                    delivered_qty,
                    cancelled_qty,
                    remaining_qty,
                    delivery_cadence,
                    deposit_amount,
                    notes,
                    status,
                    start_date,
                    version
                """
            ),
            {
                "preorder_id": preorder_id,
                "qty_increment": qty_increment,
            },
        ).mappings().first()
        if should_commit:
            session.commit()

    if row is None:
        return None
    return _preorder_record_from_row(row)
