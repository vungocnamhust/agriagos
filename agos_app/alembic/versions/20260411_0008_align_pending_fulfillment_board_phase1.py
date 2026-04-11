# pyright: reportAttributeAccessIssue=false
"""Align pending fulfillment board with Phase 1 gateway-enforced order states.

Revision ID: 20260411_0008
Revises: 20260411_0007
Create Date: 2026-04-11 00:00:08
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from typing import Any


revision = "20260411_0008"
down_revision = "20260411_0007"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


PENDING_FULFILLMENT_BOARD_SQL = """
    CREATE OR REPLACE VIEW pending_fulfillment_board AS
    SELECT
        o.order_id,
        o.order_code,
        c.full_name AS customer_name,
        o.status,
        o.delivery_date_expected AS shipping_deadline
    FROM sales_orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.status IN ('confirmed','allocated','packed','shipped')
"""


def upgrade() -> None:
    bind = alembic_op.get_bind()
    partial_order_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM sales_orders
            WHERE status IN ('partially_allocated', 'partially_packed')
            """
        )
    ).scalar_one()
    if partial_order_count:
        print(
            "[migration 20260411_0008] WARNING: found "
            f"{partial_order_count} orders in partially_* states; "
            "they will disappear from pending_fulfillment_board after this upgrade."
        )
    alembic_op.execute(PENDING_FULFILLMENT_BOARD_SQL)


def downgrade() -> None:
    # Restore the original baseline view definition for schema rollback.
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