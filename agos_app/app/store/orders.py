"""Sales order store operations."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, _to_float, is_enabled

__all__ = [
    "upsert_order",
    "fetch_order",
    "fetch_allocations_for_order",
    "replace_allocations_for_order",
    "allocate_order_atomic",
    "cancel_order_atomic",
]


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
                    tenant_id,
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
                    :tenant_id,
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
                "tenant_id": record.get("tenantId", "default"),
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
        "deliveryDateExpected": (
            order_row["delivery_date_expected"].isoformat()
            if order_row["delivery_date_expected"] else None
        ),
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
                "sourcePreorderId": (
                    str(row["source_preorder_id"]) if row["source_preorder_id"] is not None else None
                ),
                "status": row["status"],
            }
            for row in line_rows
        ],
    }


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
                {"order_line_id": item["orderLineId"], "order_id": order_id},
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
                {"lot_id": alloc["lot_id"], "qty": _to_float(alloc["allocated_qty"])},
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
