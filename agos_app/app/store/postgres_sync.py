from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal


def is_enabled() -> bool:
    return settings.postgres_write_path_enabled


def _to_float(value: Any) -> float:
    if isinstance(value, Decimal):
        return float(value)
    if value is None:
        return 0.0
    return float(value)


def customer_exists(customer_id: str) -> bool:
    if not is_enabled():
        return False

    with SessionLocal() as session:
        row = session.execute(
            text("SELECT 1 FROM customers WHERE customer_id = :customer_id"),
            {"customer_id": customer_id},
        ).first()
    return row is not None


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


def upsert_order(record: dict[str, Any]) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        session.execute(
            text(
                """
                INSERT INTO sales_orders (
                    order_id,
                    order_code,
                    customer_id,
                    channel,
                    delivery_date_expected,
                    shipping_address,
                    payment_intent,
                    note,
                    source_preorder_flag,
                    status,
                    payment_status,
                    updated_at
                ) VALUES (
                    :order_id,
                    :order_code,
                    :customer_id,
                    :channel,
                    :delivery_date_expected,
                    :shipping_address,
                    :payment_intent,
                    :note,
                    :source_preorder_flag,
                    :status,
                    :payment_status,
                    now()
                )
                ON CONFLICT (order_id) DO UPDATE SET
                    delivery_date_expected = EXCLUDED.delivery_date_expected,
                    shipping_address = EXCLUDED.shipping_address,
                    payment_intent = EXCLUDED.payment_intent,
                    note = EXCLUDED.note,
                    source_preorder_flag = EXCLUDED.source_preorder_flag,
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    updated_at = now()
                """
            ),
            {
                "order_id": record["orderId"],
                "order_code": record["orderCode"],
                "customer_id": record["customerId"],
                "channel": record["channel"],
                "delivery_date_expected": record.get("deliveryDateExpected"),
                "shipping_address": record.get("shippingAddress"),
                "payment_intent": record.get("paymentIntent"),
                "note": record.get("note"),
                "source_preorder_flag": bool(record.get("sourcePreorderFlag", False)),
                "status": record["status"],
                "payment_status": record["paymentStatus"],
            },
        )

        for line in record.get("lines", []):
            session.execute(
                text(
                    """
                    INSERT INTO sales_order_lines (
                        order_line_id,
                        order_id,
                        product_sku_id,
                        ordered_qty,
                        allocated_qty,
                        packed_qty,
                        delivered_qty,
                        unit,
                        source_preorder_id,
                        status
                    ) VALUES (
                        :order_line_id,
                        :order_id,
                        :product_sku_id,
                        :ordered_qty,
                        :allocated_qty,
                        :packed_qty,
                        :delivered_qty,
                        :unit,
                        :source_preorder_id,
                        :status
                    )
                    ON CONFLICT (order_line_id) DO UPDATE SET
                        product_sku_id = EXCLUDED.product_sku_id,
                        ordered_qty = EXCLUDED.ordered_qty,
                        allocated_qty = EXCLUDED.allocated_qty,
                        packed_qty = EXCLUDED.packed_qty,
                        delivered_qty = EXCLUDED.delivered_qty,
                        unit = EXCLUDED.unit,
                        source_preorder_id = EXCLUDED.source_preorder_id,
                        status = EXCLUDED.status
                    """
                ),
                {
                    "order_line_id": line["orderLineId"],
                    "order_id": record["orderId"],
                    "product_sku_id": line["productSkuId"],
                    "ordered_qty": line["orderedQty"],
                    "allocated_qty": line.get("allocatedQty", 0),
                    "packed_qty": line.get("packedQty", 0),
                    "delivered_qty": line.get("deliveredQty", 0),
                    "unit": line["unit"],
                    "source_preorder_id": line.get("sourcePreorderId"),
                    "status": line.get("status", "open"),
                },
            )

        session.commit()


def fetch_order(order_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        order_row = session.execute(
            text(
                """
                SELECT
                    order_id,
                    order_code,
                    customer_id,
                    channel,
                    delivery_date_expected,
                    shipping_address,
                    payment_intent,
                    note,
                    source_preorder_flag,
                    status,
                    payment_status
                FROM sales_orders
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        ).mappings().first()

        if order_row is None:
            return None

        line_rows = session.execute(
            text(
                """
                SELECT
                    order_line_id,
                    product_sku_id,
                    ordered_qty,
                    allocated_qty,
                    packed_qty,
                    delivered_qty,
                    unit,
                    source_preorder_id,
                    status
                FROM sales_order_lines
                WHERE order_id = :order_id
                ORDER BY order_line_id
                """
            ),
            {"order_id": order_id},
        ).mappings().all()

    return {
        "orderId": str(order_row["order_id"]),
        "orderCode": order_row["order_code"],
        "customerId": str(order_row["customer_id"]),
        "channel": order_row["channel"],
        "deliveryDateExpected": order_row["delivery_date_expected"].isoformat() if order_row["delivery_date_expected"] else None,
        "shippingAddress": order_row["shipping_address"],
        "paymentIntent": order_row["payment_intent"],
        "note": order_row["note"],
        "sourcePreorderFlag": bool(order_row["source_preorder_flag"]),
        "status": order_row["status"],
        "paymentStatus": order_row["payment_status"],
        "lines": [
            {
                "orderLineId": str(row["order_line_id"]),
                "productSkuId": str(row["product_sku_id"]),
                "orderedQty": _to_float(row["ordered_qty"]),
                "allocatedQty": _to_float(row["allocated_qty"]),
                "packedQty": _to_float(row["packed_qty"]),
                "deliveredQty": _to_float(row["delivered_qty"]),
                "unit": row["unit"],
                "sourcePreorderId": str(row["source_preorder_id"]) if row["source_preorder_id"] is not None else None,
                "status": row["status"],
            }
            for row in line_rows
        ],
    }


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
        "harvestOrProductionDate": row["harvest_or_production_date"].isoformat() if row["harvest_or_production_date"] else None,
        "actualQty": _to_float(row["actual_qty"]),
        "availableQty": _to_float(row["available_qty"]),
        "reservedQty": _to_float(row["reserved_qty"]),
        "releasedQty": _to_float(row["released_qty"]),
        "qualityNote": row["quality_note"],
        "status": row["status"],
    }


def replace_allocations_for_order(order_id: str, allocations: list[dict[str, Any]]) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        session.execute(
            text(
                """
                DELETE FROM allocations
                WHERE order_line_id IN (
                    SELECT order_line_id
                    FROM sales_order_lines
                    WHERE order_id = :order_id
                )
                """
            ),
            {"order_id": order_id},
        )

        for allocation in allocations:
            session.execute(
                text(
                    """
                    INSERT INTO allocations (
                        allocation_id,
                        order_line_id,
                        lot_id,
                        allocated_qty,
                        status,
                        allocated_at
                    ) VALUES (
                        :allocation_id,
                        :order_line_id,
                        :lot_id,
                        :allocated_qty,
                        :status,
                        now()
                    )
                    """
                ),
                {
                    "allocation_id": allocation["allocationId"],
                    "order_line_id": allocation["orderLineId"],
                    "lot_id": allocation["lotId"],
                    "allocated_qty": allocation["allocatedQty"],
                    "status": allocation["status"],
                },
            )

        session.commit()


def fetch_allocations_for_order(order_id: str) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    a.allocation_id,
                    a.order_line_id,
                    a.lot_id,
                    a.allocated_qty,
                    a.status
                FROM allocations a
                JOIN sales_order_lines l ON l.order_line_id = a.order_line_id
                WHERE l.order_id = :order_id
                ORDER BY a.allocation_id
                """
            ),
            {"order_id": order_id},
        ).mappings().all()

    return [
        {
            "allocationId": str(row["allocation_id"]),
            "orderLineId": str(row["order_line_id"]),
            "lotId": str(row["lot_id"]),
            "allocatedQty": _to_float(row["allocated_qty"]),
            "status": row["status"],
        }
        for row in rows
    ]


def allocate_order_atomic(
    order_id: str,
    next_status: str,
    allocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    with SessionLocal() as session:
        allocation_records: list[dict[str, Any]] = []

        for item in allocations:
            lot_row = session.execute(
                text(
                    """
                    SELECT lot_id, status, available_qty, reserved_qty
                    FROM lots
                    WHERE lot_id = :lot_id
                    FOR UPDATE
                    """
                ),
                {"lot_id": item["lotId"]},
            ).mappings().first()

            if lot_row is None:
                raise ValueError(f"Lot {item['lotId']} not found.")

            if lot_row["status"] != "released":
                raise ValueError(
                    f"Lot {item['lotId']} is not in released state (current: {lot_row['status']})."
                )

            qty = item["allocatedQty"]
            available = _to_float(lot_row["available_qty"])
            if available < qty:
                raise ValueError(
                    f"Lot {item['lotId']} has insufficient available qty ({available})."
                )

            line_row = session.execute(
                text(
                    """
                    SELECT order_line_id
                    FROM sales_order_lines
                    WHERE order_line_id = :order_line_id
                      AND order_id = :order_id
                    """
                ),
                {
                    "order_line_id": item["orderLineId"],
                    "order_id": order_id,
                },
            ).first()
            if line_row is None:
                raise ValueError(f"OrderLine {item['orderLineId']} not found.")

            session.execute(
                text(
                    """
                    UPDATE lots
                    SET
                        available_qty = available_qty - :qty,
                        reserved_qty = reserved_qty + :qty,
                        updated_at = now()
                    WHERE lot_id = :lot_id
                    """
                ),
                {"lot_id": item["lotId"], "qty": qty},
            )

            session.execute(
                text(
                    """
                    UPDATE sales_order_lines
                    SET allocated_qty = allocated_qty + :qty
                    WHERE order_line_id = :order_line_id
                    """
                ),
                {"order_line_id": item["orderLineId"], "qty": qty},
            )

            allocation_id = item["allocationId"]
            session.execute(
                text(
                    """
                    INSERT INTO allocations (
                        allocation_id,
                        order_line_id,
                        lot_id,
                        allocated_qty,
                        status,
                        allocated_at
                    ) VALUES (
                        :allocation_id,
                        :order_line_id,
                        :lot_id,
                        :allocated_qty,
                        :status,
                        now()
                    )
                    """
                ),
                {
                    "allocation_id": allocation_id,
                    "order_line_id": item["orderLineId"],
                    "lot_id": item["lotId"],
                    "allocated_qty": qty,
                    "status": item["status"],
                },
            )

            allocation_records.append(
                {
                    "allocationId": allocation_id,
                    "orderLineId": item["orderLineId"],
                    "lotId": item["lotId"],
                    "allocatedQty": qty,
                    "status": item["status"],
                }
            )

        session.execute(
            text(
                """
                UPDATE sales_orders
                SET status = :status, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": next_status},
        )

        session.commit()
        return allocation_records


def cancel_order_atomic(order_id: str, next_status: str) -> None:
    if not is_enabled():
        return

    with SessionLocal() as session:
        allocations = session.execute(
            text(
                """
                SELECT a.allocation_id, a.lot_id, a.allocated_qty
                FROM allocations a
                JOIN sales_order_lines l ON l.order_line_id = a.order_line_id
                WHERE l.order_id = :order_id
                  AND a.status <> 'cancelled'
                FOR UPDATE
                """
            ),
            {"order_id": order_id},
        ).mappings().all()

        for alloc in allocations:
            session.execute(
                text(
                    """
                    UPDATE lots
                    SET
                        available_qty = available_qty + :qty,
                        reserved_qty = GREATEST(0, reserved_qty - :qty),
                        updated_at = now()
                    WHERE lot_id = :lot_id
                    """
                ),
                {
                    "lot_id": alloc["lot_id"],
                    "qty": _to_float(alloc["allocated_qty"]),
                },
            )

        session.execute(
            text(
                """
                UPDATE allocations
                SET status = 'cancelled'
                WHERE order_line_id IN (
                    SELECT order_line_id
                    FROM sales_order_lines
                    WHERE order_id = :order_id
                )
                """
            ),
            {"order_id": order_id},
        )

        session.execute(
            text(
                """
                UPDATE sales_orders
                SET status = :status, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": next_status},
        )

        session.commit()