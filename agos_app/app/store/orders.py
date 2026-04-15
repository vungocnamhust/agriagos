"""Sales order store operations."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "upsert_order",
    "fetch_order",
    "fetch_allocation_for_order",
    "fetch_allocations_for_order",
    "replace_allocations_for_order",
    "append_inventory_movement",
    "allocate_order_atomic",
    "adjust_allocation_atomic",
    "release_allocation_atomic",
    "cancel_order_atomic",
]


def _float_value(value: Any) -> float:
    if value is None:
        return 0.0
    return float(value)


def _insert_inventory_movement(session: Any, movement: dict[str, Any]) -> None:
    session.execute(
        text(
            """
            INSERT INTO inventory_movements (
                lot_id,
                movement_type,
                qty,
                related_order_id,
                related_order_line_id,
                reason
            ) VALUES (
                :lot_id,
                :movement_type,
                :qty,
                :related_order_id,
                :related_order_line_id,
                :reason
            )
            """
        ),
        {
            "lot_id": movement["lotId"],
            "movement_type": movement["movementType"],
            "qty": movement["qty"],
            "related_order_id": movement.get("relatedOrderId"),
            "related_order_line_id": movement.get("relatedOrderLineId"),
            "reason": movement.get("reason"),
        },
    )


def append_inventory_movement(movement: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        _insert_inventory_movement(session, movement)
        if should_commit:
            session.commit()


def upsert_order(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO sales_orders (
                    order_id,
                    order_code,
                    organization_id,
                    customer_id,
                    channel,
                    delivery_date_expected,
                    shipping_address,
                    carrier,
                    tracking_ref,
                    shipped_at,
                    delivered_at,
                    proof_ref,
                    failure_reason,
                    delivery_note,
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
                    :organization_id,
                    :customer_id,
                    :channel,
                    :delivery_date_expected,
                    :shipping_address,
                    :carrier,
                    :tracking_ref,
                    :shipped_at,
                    :delivered_at,
                    :proof_ref,
                    :failure_reason,
                    :delivery_note,
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
                    carrier = EXCLUDED.carrier,
                    tracking_ref = EXCLUDED.tracking_ref,
                    shipped_at = EXCLUDED.shipped_at,
                    delivered_at = EXCLUDED.delivered_at,
                    proof_ref = EXCLUDED.proof_ref,
                    failure_reason = EXCLUDED.failure_reason,
                    delivery_note = EXCLUDED.delivery_note,
                    payment_intent = EXCLUDED.payment_intent,
                    note = EXCLUDED.note,
                    source_preorder_flag = EXCLUDED.source_preorder_flag,
                    organization_id = EXCLUDED.organization_id,
                    status = EXCLUDED.status,
                    payment_status = EXCLUDED.payment_status,
                    version = sales_orders.version + 1,
                    updated_at = now()
                """
            ),
            {
                "order_id": record["orderId"],
                "order_code": record["orderCode"],
                "organization_id": record.get("organizationId"),
                "customer_id": record["customerId"],
                "channel": record["channel"],
                "delivery_date_expected": record.get("deliveryDateExpected"),
                "shipping_address": record.get("shippingAddress"),
                "carrier": record.get("carrier"),
                "tracking_ref": record.get("trackingRef"),
                "shipped_at": record.get("shippedAt"),
                "delivered_at": record.get("deliveredAt"),
                "proof_ref": record.get("proofRef"),
                "failure_reason": record.get("failureReason"),
                "delivery_note": record.get("deliveryNote"),
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

        if should_commit:
            session.commit()


def fetch_order(order_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        order_row = session.execute(
            text(
                """
                SELECT
                    order_id,
                    tenant_id,
                    order_code,
                    organization_id,
                    customer_id,
                    channel,
                    delivery_date_expected,
                    shipping_address,
                    carrier,
                    tracking_ref,
                    shipped_at,
                    delivered_at,
                    proof_ref,
                    failure_reason,
                    delivery_note,
                    payment_intent,
                    note,
                    source_preorder_flag,
                    status,
                    payment_status,
                    version
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
        "tenantId": order_row["tenant_id"],
        "orderCode": order_row["order_code"],
        "organizationId": str(order_row["organization_id"]) if order_row["organization_id"] is not None else None,
        "customerId": str(order_row["customer_id"]),
        "channel": order_row["channel"],
        "deliveryDateExpected": (
            order_row["delivery_date_expected"].isoformat()
            if order_row["delivery_date_expected"] else None
        ),
        "shippingAddress": order_row["shipping_address"],
        "carrier": order_row["carrier"],
        "trackingRef": order_row["tracking_ref"],
        "shippedAt": order_row["shipped_at"].isoformat() if order_row["shipped_at"] else None,
        "deliveredAt": order_row["delivered_at"].isoformat() if order_row["delivered_at"] else None,
        "proofRef": order_row["proof_ref"],
        "failureReason": order_row["failure_reason"],
        "deliveryNote": order_row["delivery_note"],
        "paymentIntent": order_row["payment_intent"],
        "note": order_row["note"],
        "sourcePreorderFlag": bool(order_row["source_preorder_flag"]),
        "status": order_row["status"],
        "paymentStatus": order_row["payment_status"],
        "version": int(order_row["version"]) if order_row["version"] is not None else 1,
        "lines": [
            {
                "orderLineId": str(row["order_line_id"]),
                "productSkuId": str(row["product_sku_id"]),
                "orderedQty": _float_value(row["ordered_qty"]),
                "allocatedQty": _float_value(row["allocated_qty"]),
                "packedQty": _float_value(row["packed_qty"]),
                "deliveredQty": _float_value(row["delivered_qty"]),
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
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
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
            "allocatedQty": _float_value(row["allocated_qty"]),
            "status": row["status"],
        }
        for row in rows
    ]


def fetch_allocation_for_order(order_id: str, allocation_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
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
                  AND a.allocation_id = :allocation_id
                """
            ),
            {"order_id": order_id, "allocation_id": allocation_id},
        ).mappings().first()

    if row is None:
        return None

    return {
        "allocationId": str(row["allocation_id"]),
        "orderLineId": str(row["order_line_id"]),
        "lotId": str(row["lot_id"]),
        "allocatedQty": _float_value(row["allocated_qty"]),
        "status": row["status"],
    }


def _derive_order_status_from_line_rows(line_rows: Sequence[Any]) -> str:
    if not line_rows:
        return "confirmed"

    has_any_allocation = False
    is_fully_allocated = True
    for line in line_rows:
        ordered_qty = _float_value(line["ordered_qty"])
        allocated_qty = _float_value(line["allocated_qty"])
        if allocated_qty > 0:
            has_any_allocation = True
        if allocated_qty < ordered_qty:
            is_fully_allocated = False

    if not has_any_allocation:
        return "confirmed"
    if is_fully_allocated:
        return "allocated"
    return "partially_allocated"


def replace_allocations_for_order(order_id: str, allocations: list[dict[str, Any]]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
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

        if should_commit:
            session.commit()


def allocate_order_atomic(
    order_id: str,
    next_status: str,
    allocations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.write_session() as (session, should_commit):
        allocation_records: list[dict[str, Any]] = []
        line_totals: dict[str, float] = {}

        for item in allocations:
            line_totals[item["orderLineId"]] = line_totals.get(item["orderLineId"], 0.0) + _float_value(
                item["allocatedQty"]
            )

        preorder_totals: dict[str, float] = {}
        for order_line_id, requested_qty in line_totals.items():
            line_row = session.execute(
                text(
                    """
                    SELECT order_line_id, ordered_qty, allocated_qty, source_preorder_id
                    FROM sales_order_lines
                    WHERE order_line_id = :order_line_id
                      AND order_id = :order_id
                    FOR UPDATE
                    """
                ),
                {"order_line_id": order_line_id, "order_id": order_id},
            ).mappings().first()
            if line_row is None:
                raise ValueError(f"OrderLine {order_line_id} not found.")

            remaining_line_qty = _float_value(line_row["ordered_qty"]) - _float_value(line_row["allocated_qty"])
            if requested_qty > remaining_line_qty:
                raise ValueError(
                    f"OrderLine {order_line_id} allocation exceeds remaining qty ({remaining_line_qty})."
                )

            source_preorder_id = line_row["source_preorder_id"]
            if source_preorder_id is not None:
                preorder_id = str(source_preorder_id)
                preorder_totals[preorder_id] = preorder_totals.get(preorder_id, 0.0) + requested_qty

        for preorder_id, requested_qty in preorder_totals.items():
            preorder_row = session.execute(
                text(
                    """
                    SELECT preorder_id, remaining_qty
                    FROM preorders
                    WHERE preorder_id = :preorder_id
                    FOR UPDATE
                    """
                ),
                {"preorder_id": preorder_id},
            ).mappings().first()
            if preorder_row is None:
                raise ValueError(f"Preorder {preorder_id} not found.")

            remaining_preorder_qty = _float_value(preorder_row["remaining_qty"])
            if requested_qty > remaining_preorder_qty:
                raise ValueError(
                    f"Preorder {preorder_id} has insufficient remaining qty ({remaining_preorder_qty})."
                )

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
            available = _float_value(lot_row["available_qty"])
            if available < qty:
                raise ValueError(
                    f"Lot {item['lotId']} has insufficient available qty ({available})."
                )

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

            _insert_inventory_movement(
                session,
                {
                    "lotId": item["lotId"],
                    "movementType": "reserve",
                    "qty": qty,
                    "relatedOrderId": order_id,
                    "relatedOrderLineId": item["orderLineId"],
                    "reason": "allocation_reserved",
                },
            )

        for preorder_id, requested_qty in preorder_totals.items():
            session.execute(
                text(
                    """
                    UPDATE preorders
                    SET
                        allocated_qty = allocated_qty + :qty,
                        remaining_qty = GREATEST(0, committed_qty - (allocated_qty + :qty) - delivered_qty - cancelled_qty),
                        updated_at = now()
                    WHERE preorder_id = :preorder_id
                    """
                ),
                {"preorder_id": preorder_id, "qty": requested_qty},
            )

        session.execute(
            text(
                """
                UPDATE sales_orders
                SET status = :status, version = version + 1, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": next_status},
        )

        if should_commit:
            session.commit()
        return allocation_records


def adjust_allocation_atomic(
    order_id: str,
    allocation_id: str,
    new_allocated_qty: float,
) -> tuple[dict[str, Any], str]:
    if not _db.is_enabled():
        raise RuntimeError("Atomic allocation adjustment requires PostgreSQL")

    with _db.write_session() as (session, should_commit):
        allocation_row = session.execute(
            text(
                """
                SELECT
                    a.allocation_id,
                    a.order_line_id,
                    a.lot_id,
                    a.allocated_qty,
                    a.status,
                    l.ordered_qty,
                    l.allocated_qty AS line_allocated_qty,
                    l.source_preorder_id
                FROM allocations a
                JOIN sales_order_lines l ON l.order_line_id = a.order_line_id
                WHERE a.allocation_id = :allocation_id
                  AND l.order_id = :order_id
                FOR UPDATE
                """
            ),
            {"allocation_id": allocation_id, "order_id": order_id},
        ).mappings().first()
        if allocation_row is None:
            raise ValueError(f"Allocation {allocation_id} not found.")
        if allocation_row["status"] != "active":
            raise ValueError(
                f"Allocation {allocation_id} is not adjustable from status {allocation_row['status']}."
            )

        old_allocated_qty = _float_value(allocation_row["allocated_qty"])
        delta = _float_value(new_allocated_qty) - old_allocated_qty
        if delta == 0:
            line_rows = session.execute(
                text(
                    """
                    SELECT ordered_qty, allocated_qty
                    FROM sales_order_lines
                    WHERE order_id = :order_id
                    """
                ),
                {"order_id": order_id},
            ).mappings().all()
            order_status = _derive_order_status_from_line_rows(line_rows)
            if should_commit:
                session.commit()
            return (
                {
                    "allocationId": str(allocation_row["allocation_id"]),
                    "orderLineId": str(allocation_row["order_line_id"]),
                    "lotId": str(allocation_row["lot_id"]),
                    "allocatedQty": old_allocated_qty,
                    "status": allocation_row["status"],
                },
                order_status,
            )

        lot_row = session.execute(
            text(
                """
                SELECT lot_id, status, available_qty, reserved_qty
                FROM lots
                WHERE lot_id = :lot_id
                FOR UPDATE
                """
            ),
            {"lot_id": allocation_row["lot_id"]},
        ).mappings().first()
        if lot_row is None:
            raise ValueError(f"Lot {allocation_row['lot_id']} not found.")
        if lot_row["status"] != "released":
            raise ValueError(
                f"Lot {allocation_row['lot_id']} is not in released state (current: {lot_row['status']})."
            )

        if delta > 0:
            available_qty = _float_value(lot_row["available_qty"])
            if available_qty < delta:
                raise ValueError(
                    f"Lot {allocation_row['lot_id']} has insufficient available qty ({available_qty})."
                )

            remaining_line_qty = _float_value(allocation_row["ordered_qty"]) - _float_value(
                allocation_row["line_allocated_qty"]
            )
            if delta > remaining_line_qty:
                raise ValueError(
                    f"OrderLine {allocation_row['order_line_id']} allocation exceeds remaining qty ({remaining_line_qty})."
                )

            source_preorder_id = allocation_row["source_preorder_id"]
            if source_preorder_id is not None:
                preorder_row = session.execute(
                    text(
                        """
                        SELECT preorder_id, remaining_qty
                        FROM preorders
                        WHERE preorder_id = :preorder_id
                        FOR UPDATE
                        """
                    ),
                    {"preorder_id": source_preorder_id},
                ).mappings().first()
                if preorder_row is None:
                    raise ValueError(f"Preorder {source_preorder_id} not found.")
                remaining_preorder_qty = _float_value(preorder_row["remaining_qty"])
                if delta > remaining_preorder_qty:
                    raise ValueError(
                        f"Preorder {source_preorder_id} has insufficient remaining qty ({remaining_preorder_qty})."
                    )
                session.execute(
                    text(
                        """
                        UPDATE preorders
                        SET
                            allocated_qty = allocated_qty + :delta,
                            remaining_qty = GREATEST(0, committed_qty - (allocated_qty + :delta) - delivered_qty - cancelled_qty),
                            updated_at = now()
                        WHERE preorder_id = :preorder_id
                        """
                    ),
                    {"preorder_id": source_preorder_id, "delta": delta},
                )

            session.execute(
                text(
                    """
                    UPDATE lots
                    SET
                        available_qty = available_qty - :delta,
                        reserved_qty = reserved_qty + :delta,
                        updated_at = now()
                    WHERE lot_id = :lot_id
                    """
                ),
                {"lot_id": allocation_row["lot_id"], "delta": delta},
            )
            session.execute(
                text(
                    """
                    UPDATE sales_order_lines
                    SET allocated_qty = allocated_qty + :delta
                    WHERE order_line_id = :order_line_id
                    """
                ),
                {"order_line_id": allocation_row["order_line_id"], "delta": delta},
            )
            _insert_inventory_movement(
                session,
                {
                    "lotId": str(allocation_row["lot_id"]),
                    "movementType": "reserve",
                    "qty": delta,
                    "relatedOrderId": order_id,
                    "relatedOrderLineId": str(allocation_row["order_line_id"]),
                    "reason": "allocation_adjusted_up",
                },
            )
        else:
            release_qty = abs(delta)
            source_preorder_id = allocation_row["source_preorder_id"]
            if source_preorder_id is not None:
                session.execute(
                    text(
                        """
                        UPDATE preorders
                        SET
                            allocated_qty = GREATEST(0, allocated_qty - :release_qty),
                            remaining_qty = GREATEST(0, committed_qty - GREATEST(0, allocated_qty - :release_qty) - delivered_qty - cancelled_qty),
                            updated_at = now()
                        WHERE preorder_id = :preorder_id
                        """
                    ),
                    {"preorder_id": source_preorder_id, "release_qty": release_qty},
                )

            session.execute(
                text(
                    """
                    UPDATE lots
                    SET
                        available_qty = available_qty + :release_qty,
                        reserved_qty = GREATEST(0, reserved_qty - :release_qty),
                        updated_at = now()
                    WHERE lot_id = :lot_id
                    """
                ),
                {"lot_id": allocation_row["lot_id"], "release_qty": release_qty},
            )
            session.execute(
                text(
                    """
                    UPDATE sales_order_lines
                    SET allocated_qty = GREATEST(0, allocated_qty - :release_qty)
                    WHERE order_line_id = :order_line_id
                    """
                ),
                {"order_line_id": allocation_row["order_line_id"], "release_qty": release_qty},
            )
            _insert_inventory_movement(
                session,
                {
                    "lotId": str(allocation_row["lot_id"]),
                    "movementType": "release_reservation",
                    "qty": release_qty,
                    "relatedOrderId": order_id,
                    "relatedOrderLineId": str(allocation_row["order_line_id"]),
                    "reason": "allocation_adjusted_down",
                },
            )

        session.execute(
            text(
                """
                UPDATE allocations
                SET allocated_qty = :new_allocated_qty
                WHERE allocation_id = :allocation_id
                """
            ),
            {"allocation_id": allocation_id, "new_allocated_qty": new_allocated_qty},
        )

        line_rows = session.execute(
            text(
                """
                SELECT ordered_qty, allocated_qty
                FROM sales_order_lines
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        ).mappings().all()
        order_status = _derive_order_status_from_line_rows(line_rows)
        session.execute(
            text(
                """
                UPDATE sales_orders
                SET status = :status, version = version + 1, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": order_status},
        )

        if should_commit:
            session.commit()
        return (
            {
                "allocationId": str(allocation_row["allocation_id"]),
                "orderLineId": str(allocation_row["order_line_id"]),
                "lotId": str(allocation_row["lot_id"]),
                "allocatedQty": _float_value(new_allocated_qty),
                "status": allocation_row["status"],
            },
            order_status,
        )


def release_allocation_atomic(order_id: str, allocation_id: str) -> tuple[dict[str, Any], str]:
    if not _db.is_enabled():
        raise RuntimeError("Atomic allocation release requires PostgreSQL")

    with _db.write_session() as (session, should_commit):
        allocation_row = session.execute(
            text(
                """
                SELECT
                    a.allocation_id,
                    a.order_line_id,
                    a.lot_id,
                    a.allocated_qty,
                    a.status,
                    l.source_preorder_id
                FROM allocations a
                JOIN sales_order_lines l ON l.order_line_id = a.order_line_id
                WHERE a.allocation_id = :allocation_id
                  AND l.order_id = :order_id
                FOR UPDATE
                """
            ),
            {"allocation_id": allocation_id, "order_id": order_id},
        ).mappings().first()
        if allocation_row is None:
            raise ValueError(f"Allocation {allocation_id} not found.")
        if allocation_row["status"] != "active":
            raise ValueError(
                f"Allocation {allocation_id} is not releasable from status {allocation_row['status']}."
            )

        release_qty = _float_value(allocation_row["allocated_qty"])
        session.execute(
            text(
                """
                UPDATE lots
                SET
                    available_qty = available_qty + :release_qty,
                    reserved_qty = GREATEST(0, reserved_qty - :release_qty),
                    updated_at = now()
                WHERE lot_id = :lot_id
                """
            ),
            {"lot_id": allocation_row["lot_id"], "release_qty": release_qty},
        )
        session.execute(
            text(
                """
                UPDATE sales_order_lines
                SET allocated_qty = GREATEST(0, allocated_qty - :release_qty)
                WHERE order_line_id = :order_line_id
                """
            ),
            {"order_line_id": allocation_row["order_line_id"], "release_qty": release_qty},
        )
        if allocation_row["source_preorder_id"] is not None:
            session.execute(
                text(
                    """
                    UPDATE preorders
                    SET
                        allocated_qty = GREATEST(0, allocated_qty - :release_qty),
                        remaining_qty = GREATEST(0, committed_qty - GREATEST(0, allocated_qty - :release_qty) - delivered_qty - cancelled_qty),
                        updated_at = now()
                    WHERE preorder_id = :preorder_id
                    """
                ),
                {"preorder_id": allocation_row["source_preorder_id"], "release_qty": release_qty},
            )

        session.execute(
            text(
                """
                UPDATE allocations
                SET status = 'released'
                WHERE allocation_id = :allocation_id
                """
            ),
            {"allocation_id": allocation_id},
        )
        _insert_inventory_movement(
            session,
            {
                "lotId": str(allocation_row["lot_id"]),
                "movementType": "release_reservation",
                "qty": release_qty,
                "relatedOrderId": order_id,
                "relatedOrderLineId": str(allocation_row["order_line_id"]),
                "reason": "allocation_released",
            },
        )

        line_rows = session.execute(
            text(
                """
                SELECT ordered_qty, allocated_qty
                FROM sales_order_lines
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id},
        ).mappings().all()
        order_status = _derive_order_status_from_line_rows(line_rows)
        session.execute(
            text(
                """
                UPDATE sales_orders
                SET status = :status, version = version + 1, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": order_status},
        )

        if should_commit:
            session.commit()
        return (
            {
                "allocationId": str(allocation_row["allocation_id"]),
                "orderLineId": str(allocation_row["order_line_id"]),
                "lotId": str(allocation_row["lot_id"]),
                "allocatedQty": release_qty,
                "status": "released",
            },
            order_status,
        )


def cancel_order_atomic(order_id: str, next_status: str) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        allocations = session.execute(
            text(
                """
                                SELECT a.allocation_id, a.lot_id, a.allocated_qty, a.order_line_id, l.source_preorder_id
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
            qty = _float_value(alloc["allocated_qty"])
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
                {"lot_id": alloc["lot_id"], "qty": qty},
            )

            session.execute(
                text(
                    """
                    UPDATE sales_order_lines
                    SET allocated_qty = GREATEST(0, allocated_qty - :qty)
                    WHERE order_line_id = :order_line_id
                    """
                ),
                {"order_line_id": alloc["order_line_id"], "qty": qty},
            )

            if alloc["source_preorder_id"] is not None:
                session.execute(
                    text(
                        """
                        UPDATE preorders
                        SET
                            allocated_qty = GREATEST(0, allocated_qty - :qty),
                            remaining_qty = GREATEST(0, committed_qty - GREATEST(0, allocated_qty - :qty) - delivered_qty - cancelled_qty),
                            updated_at = now()
                        WHERE preorder_id = :preorder_id
                        """
                    ),
                    {"preorder_id": alloc["source_preorder_id"], "qty": qty},
                )

            _insert_inventory_movement(
                session,
                {
                    "lotId": str(alloc["lot_id"]),
                    "movementType": "release_reservation",
                    "qty": qty,
                    "relatedOrderId": order_id,
                    "relatedOrderLineId": str(alloc["order_line_id"]),
                    "reason": "allocation_cancelled",
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
                SET status = :status, version = version + 1, updated_at = now()
                WHERE order_id = :order_id
                """
            ),
            {"order_id": order_id, "status": next_status},
        )

        if should_commit:
            session.commit()
