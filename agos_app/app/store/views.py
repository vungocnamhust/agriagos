"""Read-model query helpers for view endpoints."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, _to_float, is_enabled

__all__ = [
    "fetch_available_lots_board",
    "fetch_customer_360",
    "fetch_pending_fulfillment_board",
]


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def fetch_customer_360(customer_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        customer_row = session.execute(
            text(
                """
                SELECT
                    customer_id,
                    customer_code,
                    full_name,
                    phone,
                    channel_source,
                    default_address,
                    district,
                    province,
                    status,
                    tags,
                    notes,
                    last_order_at,
                    created_at
                FROM customers
                WHERE customer_id = CAST(:customer_id AS uuid)
                """
            ),
            {"customer_id": customer_id},
        ).mappings().first()

        if customer_row is None:
            return None

        preference_rows = session.execute(
            text(
                """
                SELECT preference_type, preference_value, confidence_level
                FROM customer_preferences
                WHERE customer_id = CAST(:customer_id AS uuid)
                ORDER BY updated_at DESC, preference_type, preference_value
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

        preorder_rows = session.execute(
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
                    status
                FROM preorders
                WHERE customer_id = CAST(:customer_id AS uuid)
                  AND status = 'active'
                ORDER BY created_at DESC, preorder_id DESC
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

        order_rows = session.execute(
            text(
                """
                SELECT
                    order_id,
                    order_code,
                    customer_id,
                    channel,
                    status,
                    payment_status,
                    delivery_date_expected
                FROM sales_orders
                WHERE customer_id = CAST(:customer_id AS uuid)
                ORDER BY created_at DESC, order_id DESC
                LIMIT 10
                """
            ),
            {"customer_id": customer_id},
        ).mappings().all()

        recent_orders: list[dict[str, Any]] = []
        for order_row in order_rows:
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
                        source_preorder_id
                    FROM sales_order_lines
                    WHERE order_id = :order_id
                    ORDER BY order_line_id
                    """
                ),
                {"order_id": order_row["order_id"]},
            ).mappings().all()

            recent_orders.append(
                {
                    "orderId": str(order_row["order_id"]),
                    "orderCode": order_row["order_code"],
                    "customerId": str(order_row["customer_id"]),
                    "channel": order_row["channel"],
                    "status": order_row["status"],
                    "paymentStatus": order_row["payment_status"],
                    "deliveryDateExpected": _iso(order_row["delivery_date_expected"]),
                    "lines": [
                        {
                            "orderLineId": str(line_row["order_line_id"]),
                            "productSkuId": str(line_row["product_sku_id"]),
                            "orderedQty": _to_float(line_row["ordered_qty"]),
                            "allocatedQty": _to_float(line_row["allocated_qty"]),
                            "packedQty": _to_float(line_row["packed_qty"]),
                            "deliveredQty": _to_float(line_row["delivered_qty"]),
                            "unit": line_row["unit"],
                            "sourcePreorderId": (
                                str(line_row["source_preorder_id"])
                                if line_row["source_preorder_id"] is not None else None
                            ),
                        }
                        for line_row in line_rows
                    ],
                }
            )

    return {
        "customer": {
            "customerId": str(customer_row["customer_id"]),
            "customerCode": customer_row["customer_code"],
            "fullName": customer_row["full_name"],
            "phone": customer_row["phone"],
            "status": customer_row["status"],
            "createdAt": _iso(customer_row["created_at"]),
            "tags": list(customer_row["tags"] or []),
            "channelSource": customer_row["channel_source"],
            "defaultAddress": customer_row["default_address"],
            "district": customer_row["district"],
            "province": customer_row["province"],
            "notes": customer_row["notes"],
            "lastOrderAt": _iso(customer_row["last_order_at"]),
        },
        "activePreorders": [
            {
                "preorderId": str(row["preorder_id"]),
                "preorderCode": row["preorder_code"],
                "customerId": str(row["customer_id"]),
                "productSkuId": str(row["product_sku_id"]),
                "committedQty": _to_float(row["committed_qty"]),
                "allocatedQty": _to_float(row["allocated_qty"]),
                "deliveredQty": _to_float(row["delivered_qty"]),
                "remainingQty": _to_float(row["remaining_qty"]),
                "status": row["status"],
            }
            for row in preorder_rows
        ],
        "recentOrders": recent_orders,
        "preferences": [
            {
                "preferenceType": row["preference_type"],
                "preferenceValue": row["preference_value"],
                "confidenceLevel": _to_float(row["confidence_level"]),
            }
            for row in preference_rows
        ],
    }


def fetch_available_lots_board(product_sku_id: str | None) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    query = """
        SELECT lot_id, lot_code, product_sku_id, released_qty, available_qty, status
        FROM available_lots_board
    """
    params: dict[str, Any] = {}
    if product_sku_id is not None:
        query += " WHERE product_sku_id = CAST(:product_sku_id AS uuid)"
        params["product_sku_id"] = product_sku_id
    query += " ORDER BY harvest_or_production_date DESC, lot_code"

    with SessionLocal() as session:
        rows = session.execute(text(query), params).mappings().all()

    return [
        {
            "lotId": str(row["lot_id"]),
            "lotCode": row["lot_code"],
            "productSkuId": str(row["product_sku_id"]),
            "releasedQty": _to_float(row["released_qty"]),
            "availableQty": _to_float(row["available_qty"]),
            "status": row["status"],
        }
        for row in rows
    ]


def fetch_pending_fulfillment_board() -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT order_id, order_code, customer_name, status, shipping_deadline
                FROM pending_fulfillment_board
                ORDER BY shipping_deadline NULLS LAST, order_code
                """
            )
        ).mappings().all()

    return [
        {
            "orderId": str(row["order_id"]),
            "orderCode": row["order_code"],
            "customerName": row["customer_name"],
            "status": row["status"],
            "shippingDeadline": _iso(row["shipping_deadline"]),
        }
        for row in rows
    ]