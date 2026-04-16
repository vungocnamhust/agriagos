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
    "fetch_project_order_allocation_summary",
    "fetch_project_contribution_summary",
    "fetch_project_pnl_summary",
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
        SELECT lot_id, lot_code, organization_id, product_sku_id, released_qty, available_qty, status
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
            "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
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
                    plot_organization_id,
                    plot_name,
                    location_text,
                    area_value,
                    area_unit,
                    plot_status,
                    crop_cycle_id,
                    crop_cycle_organization_id,
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
            "plotOrganizationId": str(row["plot_organization_id"]) if row["plot_organization_id"] is not None else None,
            "plotName": row["plot_name"],
            "locationText": row["location_text"],
            "areaValue": _db.to_float(row["area_value"]),
            "areaUnit": row["area_unit"],
            "plotStatus": row["plot_status"],
            "cropCycleId": str(row["crop_cycle_id"]) if row["crop_cycle_id"] is not None else None,
            "cropCycleOrganizationId": (
                str(row["crop_cycle_organization_id"])
                if row["crop_cycle_organization_id"] is not None else None
            ),
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
                SELECT order_id, order_code, organization_id, customer_name, status, shipping_deadline
                FROM pending_fulfillment_board
                ORDER BY shipping_deadline NULLS LAST, order_code
                """
            )
        ).mappings().all()

    return [
        {
            "orderId": str(row["order_id"]),
            "orderCode": row["order_code"],
            "organizationId": str(row["organization_id"]) if row["organization_id"] is not None else None,
            "customerName": row["customer_name"],
            "status": row["status"],
            "shippingDeadline": _iso(row["shipping_deadline"]),
        }
        for row in rows
    ]


def fetch_project_contribution_summary(project_scope_id: str | None = None) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    query = """
        SELECT
            ps.project_scope_id,
            ps.project_scope_code,
            ps.name AS project_scope_name,
            COUNT(*) FILTER (WHERE pce.status = 'proposed') AS proposed_count,
            COUNT(*) FILTER (WHERE pce.status = 'confirmed') AS confirmed_count,
            COUNT(*) FILTER (WHERE pce.status = 'rejected') AS rejected_count,
            COALESCE(SUM(pce.quantity) FILTER (WHERE pce.status = 'confirmed'), 0) AS confirmed_quantity,
            SUM(pce.estimated_value) FILTER (WHERE pce.status = 'confirmed') AS confirmed_estimated_value,
            CASE
                WHEN COUNT(DISTINCT pce.currency) FILTER (WHERE pce.status = 'confirmed' AND pce.currency IS NOT NULL) = 1
                    THEN MAX(pce.currency) FILTER (WHERE pce.status = 'confirmed')
                ELSE NULL
            END AS currency
        FROM project_scopes ps
        JOIN project_contribution_events pce ON pce.project_scope_id = ps.project_scope_id
    """
    params: dict[str, Any] = {}
    if project_scope_id is not None:
        query += " WHERE ps.project_scope_id = CAST(:project_scope_id AS uuid)"
        params["project_scope_id"] = project_scope_id
    query += """
        GROUP BY ps.project_scope_id, ps.project_scope_code, ps.name
        ORDER BY ps.project_scope_code
    """

    with SessionLocal() as session:
        rows = session.execute(text(query), params).mappings().all()

    return [
        {
            "projectScopeId": str(row["project_scope_id"]),
            "projectScopeCode": row["project_scope_code"],
            "projectScopeName": row["project_scope_name"],
            "proposedCount": int(row["proposed_count"]),
            "confirmedCount": int(row["confirmed_count"]),
            "rejectedCount": int(row["rejected_count"]),
            "confirmedQuantity": _db.to_float(row["confirmed_quantity"]),
            "confirmedEstimatedValue": _db.to_float(row["confirmed_estimated_value"]) if row["confirmed_estimated_value"] is not None else None,
            "currency": row["currency"],
        }
        for row in rows
    ]


def fetch_project_pnl_summary(project_scope_id: str | None = None) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    query = """
        SELECT
            ps.project_scope_id,
            ps.project_scope_code,
            ps.name AS project_scope_name,
            COALESCE(costs.cost_record_count, 0) AS cost_record_count,
            COALESCE(revenues.revenue_record_count, 0) AS revenue_record_count,
            COALESCE(costs.recognized_cost_amount, 0) AS recognized_cost_amount,
            COALESCE(revenues.recognized_revenue_net_amount, 0) AS recognized_revenue_net_amount,
            COALESCE(revenues.recognized_revenue_net_amount, 0) - COALESCE(costs.recognized_cost_amount, 0) AS margin_amount,
            CASE
                WHEN costs.currency IS NOT NULL AND revenues.currency IS NOT NULL AND costs.currency <> revenues.currency THEN NULL
                ELSE COALESCE(revenues.currency, costs.currency)
            END AS currency
        FROM project_scopes ps
        LEFT JOIN (
            SELECT
                project_scope_id,
                COUNT(*) AS cost_record_count,
                SUM(amount) AS recognized_cost_amount,
                CASE
                    WHEN COUNT(DISTINCT currency) FILTER (WHERE currency IS NOT NULL) = 1 THEN MAX(currency)
                    ELSE NULL
                END AS currency
            FROM project_cost_records
            GROUP BY project_scope_id
        ) costs ON costs.project_scope_id = ps.project_scope_id
        LEFT JOIN (
            SELECT
                project_scope_id,
                COUNT(*) AS revenue_record_count,
                SUM(net_amount) AS recognized_revenue_net_amount,
                CASE
                    WHEN COUNT(DISTINCT currency) FILTER (WHERE currency IS NOT NULL) = 1 THEN MAX(currency)
                    ELSE NULL
                END AS currency
            FROM project_revenue_records
            GROUP BY project_scope_id
        ) revenues ON revenues.project_scope_id = ps.project_scope_id
    """
    params: dict[str, Any] = {}
    if project_scope_id is not None:
        query += " WHERE ps.project_scope_id = CAST(:project_scope_id AS uuid)"
        params["project_scope_id"] = project_scope_id
    query += """
        ORDER BY ps.project_scope_code
    """

    with SessionLocal() as session:
        rows = session.execute(text(query), params).mappings().all()

    return [
        {
            "projectScopeId": str(row["project_scope_id"]),
            "projectScopeCode": row["project_scope_code"],
            "projectScopeName": row["project_scope_name"],
            "costRecordCount": int(row["cost_record_count"]),
            "revenueRecordCount": int(row["revenue_record_count"]),
            "recognizedCostAmount": _db.to_float(row["recognized_cost_amount"]),
            "recognizedRevenueNetAmount": _db.to_float(row["recognized_revenue_net_amount"]),
            "marginAmount": _db.to_float(row["margin_amount"]),
            "currency": row["currency"],
        }
        for row in rows
        if int(row["cost_record_count"] or 0) > 0 or int(row["revenue_record_count"] or 0) > 0
    ]


def fetch_project_order_allocation_summary(project_scope_id: str | None = None) -> list[dict[str, Any]]:
    if not is_enabled():
        return []

    query = """
        WITH assigned_orders AS (
            SELECT DISTINCT
                pa.project_scope_id,
                pa.target_id AS order_id
            FROM project_assignments pa
            WHERE pa.target_type = 'order'
              AND pa.ended_at IS NULL
    """
    params: dict[str, Any] = {}
    if project_scope_id is not None:
        query += " AND pa.project_scope_id = CAST(:project_scope_id AS uuid)"
        params["project_scope_id"] = project_scope_id
    query += """
        )
        SELECT
            ps.project_scope_id,
            ps.project_scope_code,
            ps.name AS project_scope_name,
            COUNT(DISTINCT ao.order_id) AS assigned_order_count,
            COUNT(DISTINCT ao.order_id) FILTER (WHERE a.allocation_id IS NOT NULL) AS allocated_order_count,
            COUNT(a.allocation_id) AS allocation_count,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'active') AS active_allocation_count,
            COUNT(a.allocation_id) FILTER (WHERE a.status = 'released') AS released_allocation_count,
            COALESCE(SUM(a.allocated_qty), 0) AS allocated_qty,
            COALESCE(SUM(a.allocated_qty) FILTER (WHERE a.status = 'active'), 0) AS active_allocated_qty,
            COALESCE(SUM(a.allocated_qty) FILTER (WHERE a.status = 'released'), 0) AS released_allocated_qty,
            CASE
                WHEN COUNT(DISTINCT l.unit) FILTER (WHERE a.allocation_id IS NOT NULL AND l.unit IS NOT NULL) = 1
                    THEN MAX(l.unit) FILTER (WHERE a.allocation_id IS NOT NULL)
                ELSE NULL
            END AS unit
        FROM assigned_orders ao
        JOIN project_scopes ps ON ps.project_scope_id = ao.project_scope_id
        LEFT JOIN sales_orders o ON o.order_id = ao.order_id
        LEFT JOIN sales_order_lines l ON l.order_id = o.order_id
        LEFT JOIN allocations a ON a.order_line_id = l.order_line_id
        GROUP BY ps.project_scope_id, ps.project_scope_code, ps.name
        ORDER BY ps.project_scope_code
    """

    with SessionLocal() as session:
        rows = session.execute(text(query), params).mappings().all()

    return [
        {
            "projectScopeId": str(row["project_scope_id"]),
            "projectScopeCode": row["project_scope_code"],
            "projectScopeName": row["project_scope_name"],
            "assignedOrderCount": int(row["assigned_order_count"]),
            "allocatedOrderCount": int(row["allocated_order_count"]),
            "allocationCount": int(row["allocation_count"]),
            "activeAllocationCount": int(row["active_allocation_count"]),
            "releasedAllocationCount": int(row["released_allocation_count"]),
            "allocatedQty": _db.to_float(row["allocated_qty"]),
            "activeAllocatedQty": _db.to_float(row["active_allocated_qty"]),
            "releasedAllocatedQty": _db.to_float(row["released_allocated_qty"]),
            "unit": row["unit"],
        }
        for row in rows
    ]