# pyright: reportAttributeAccessIssue=false
"""Create Phase 1 operational views.

Revision ID: 20260410_0006
Revises: 20260410_0005
Create Date: 2026-04-10 00:00:06
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260410_0006"
down_revision = "20260410_0005"
branch_labels = None
depends_on = None

alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.execute(
        """
        CREATE OR REPLACE VIEW available_lots_board AS
        SELECT
            l.lot_id,
            l.lot_code,
            l.product_sku_id,
            p.sku_code,
            p.sku_name,
            l.released_qty,
            l.available_qty,
            l.status,
            l.harvest_or_production_date
        FROM lots l
        JOIN product_skus p ON p.product_sku_id = l.product_sku_id
        WHERE l.status = 'released'
        """
    )
    alembic_op.execute(
        """
        CREATE OR REPLACE VIEW pending_fulfillment_board AS
        SELECT
            o.order_id,
            o.order_code,
            c.full_name AS customer_name,
            o.status,
            o.delivery_date_expected AS shipping_deadline
        FROM sales_orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.status IN ('confirmed','allocated','partially_allocated','packed','partially_packed','shipped')
        """
    )
    alembic_op.execute(
        """
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
    )


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS customer_360_view")
    alembic_op.execute("DROP VIEW IF EXISTS pending_fulfillment_board")
    alembic_op.execute("DROP VIEW IF EXISTS available_lots_board")