"""Read-model query helpers for view endpoints."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.store import _db

__all__ = [
    "fetch_available_lots_board",
    "fetch_customer_360",
    "fetch_farm_summary_board",
    "fetch_pending_fulfillment_board",
    "is_enabled",
    "SessionLocal",
]


def is_enabled() -> bool:
    return _db.is_enabled()


def SessionLocal():
    return _db.SessionLocal()


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _normalize_growth_stage(value: str | None) -> str | None:
    if value == "flowering_or_maturing":
        return "maturing"
    return value


def _json_value(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    return fallback


def fetch_customer_360(customer_id: str) -> dict[str, Any] | None:
    if not is_enabled():
        return None

    with SessionLocal() as session:
        row = session.execute(
            text(
                """
                SELECT
                    customer_id,
                    customer,
                    active_preorders,
                    recent_orders,
                    preferences
                FROM customer_360_view
                WHERE customer_id = CAST(:customer_id AS uuid)
                """
            ),
            {"customer_id": customer_id},
        ).mappings().first()

        if row is None:
            return None

    return {
        "customer": _json_value(row["customer"], {}),
        "activePreorders": _json_value(row["active_preorders"], []),
        "recentOrders": _json_value(row["recent_orders"], []),
        "preferences": _json_value(row["preferences"], []),
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
            "releasedQty": _db.to_float(row["released_qty"]),
            "availableQty": _db.to_float(row["available_qty"]),
            "status": row["status"],
        }
        for row in rows
    ]


def fetch_farm_summary_board() -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    with SessionLocal() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    plot_id,
                    plot_code,
                    plot_name,
                    location_text,
                    area_value,
                    area_unit,
                    plot_status,
                    crop_cycle_id,
                    crop_name,
                    growth_stage,
                    crop_cycle_status,
                    expected_harvest_from,
                    expected_harvest_to,
                    estimated_yield_qty
                FROM farm_summary_board
                ORDER BY expected_harvest_from NULLS LAST, plot_code, crop_cycle_id NULLS LAST
                """
            )
        ).mappings().all()

    return [
        {
            "plotId": str(row["plot_id"]),
            "plotCode": row["plot_code"],
            "plotName": row["plot_name"],
            "locationText": row["location_text"],
            "areaValue": _db.to_float(row["area_value"]),
            "areaUnit": row["area_unit"],
            "plotStatus": row["plot_status"],
            "cropCycleId": str(row["crop_cycle_id"]) if row["crop_cycle_id"] is not None else None,
            "cropName": row["crop_name"],
            "growthStage": _normalize_growth_stage(row["growth_stage"]),
            "cropCycleStatus": row["crop_cycle_status"],
            "expectedHarvestFrom": _iso(row["expected_harvest_from"]),
            "expectedHarvestTo": _iso(row["expected_harvest_to"]),
            "estimatedYieldQty": (
                _db.to_float(row["estimated_yield_qty"])
                if row["estimated_yield_qty"] is not None else None
            ),
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