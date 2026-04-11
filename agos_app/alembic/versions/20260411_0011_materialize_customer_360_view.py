# pyright: reportAttributeAccessIssue=false
"""Materialize customer 360 detail projection view.

This replaces the simpler scalar customer_360_view introduced in
20260410_0006_phase1_views with a nested JSON projection that matches the
runtime Customer360View contract.

Revision ID: 20260411_0011
Revises: 20260411_0010
Create Date: 2026-04-11 00:00:11
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260411_0011"
down_revision = "20260411_0010"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


CUSTOMER_360_VIEW_SQL = """
    CREATE OR REPLACE VIEW customer_360_view AS
    SELECT
        c.customer_id,
        jsonb_build_object(
            'customerId', c.customer_id,
            'customerCode', c.customer_code,
            'fullName', c.full_name,
            'phone', c.phone,
            'status', c.status,
            'createdAt', c.created_at,
            'tags', c.tags,
            'channelSource', c.channel_source,
            'defaultAddress', c.default_address,
            'district', c.district,
            'province', c.province,
            'notes', c.notes,
            'lastOrderAt', c.last_order_at
        ) AS customer,
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'preorderId', p.preorder_id,
                        'preorderCode', p.preorder_code,
                        'customerId', p.customer_id,
                        'productSkuId', p.product_sku_id,
                        'committedQty', p.committed_qty,
                        'allocatedQty', p.allocated_qty,
                        'deliveredQty', p.delivered_qty,
                        'remainingQty', p.remaining_qty,
                        'status', p.status,
                        'startDate', p.start_date
                    )
                    ORDER BY p.created_at DESC, p.preorder_id DESC
                )
                FROM preorders p
                WHERE p.customer_id = c.customer_id
                  AND p.status = 'active'
            ),
            '[]'::jsonb
        ) AS active_preorders,
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'orderId', o.order_id,
                        'orderCode', o.order_code,
                        'customerId', o.customer_id,
                        'orderDate', o.order_date,
                        'channel', o.channel,
                        'status', o.status,
                        'paymentStatus', o.payment_status,
                        'deliveryDateExpected', o.delivery_date_expected,
                        'shippingAddress', o.shipping_address,
                        'note', o.note,
                        'createdBy', o.created_by,
                        'sourcePreorderFlag', o.source_preorder_flag,
                        'lines', COALESCE(
                            (
                                SELECT jsonb_agg(
                                    jsonb_build_object(
                                        'orderLineId', sol.order_line_id,
                                        'productSkuId', sol.product_sku_id,
                                        'orderedQty', sol.ordered_qty,
                                        'allocatedQty', sol.allocated_qty,
                                        'packedQty', sol.packed_qty,
                                        'deliveredQty', sol.delivered_qty,
                                        'unit', sol.unit,
                                        'status', sol.status,
                                        'sourcePreorderId', sol.source_preorder_id
                                    )
                                    ORDER BY sol.order_line_id
                                )
                                FROM sales_order_lines sol
                                WHERE sol.order_id = o.order_id
                            ),
                            '[]'::jsonb
                        )
                    )
                    ORDER BY o.created_at DESC, o.order_id DESC
                )
                FROM (
                    SELECT *
                    FROM sales_orders
                    WHERE customer_id = c.customer_id
                    ORDER BY created_at DESC, order_id DESC
                    LIMIT 10
                ) o
            ),
            '[]'::jsonb
        ) AS recent_orders,
        COALESCE(
            (
                SELECT jsonb_agg(
                    jsonb_build_object(
                        'preferenceType', cp.preference_type,
                        'preferenceValue', cp.preference_value,
                        'confidenceLevel', cp.confidence_level
                    )
                    ORDER BY cp.updated_at DESC, cp.preference_type, cp.preference_value
                )
                FROM customer_preferences cp
                WHERE cp.customer_id = c.customer_id
            ),
            '[]'::jsonb
        ) AS preferences
    FROM customers c
"""


BASELINE_CUSTOMER_360_VIEW_SQL = """
    CREATE OR REPLACE VIEW customer_360_view AS
    SELECT
        c.customer_id,
        c.customer_code,
        c.full_name,
        c.phone,
        c.tags,
        c.last_order_at,
        (
            SELECT COUNT(*) FROM sales_orders o WHERE o.customer_id = c.customer_id
        ) AS total_orders,
        (
            SELECT COUNT(*) FROM preorders p WHERE p.customer_id = c.customer_id AND p.status IN ('confirmed','active')
        ) AS active_preorders
    FROM customers c
"""


def upgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS customer_360_view")
    alembic_op.execute(CUSTOMER_360_VIEW_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS customer_360_view")
    alembic_op.execute(BASELINE_CUSTOMER_360_VIEW_SQL)