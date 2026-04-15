"""Refresh pending fulfillment board for organization id propagation.

Revision ID: 20260416_0024
Revises: 20260416_0023
Create Date: 2026-04-16 11:10:00
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260416_0024"
down_revision = "20260416_0023"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


UPDATED_PENDING_FULFILLMENT_BOARD_SQL = """
    CREATE OR REPLACE VIEW pending_fulfillment_board AS
    SELECT
        o.order_id,
        o.order_code,
        o.organization_id,
        c.full_name AS customer_name,
        o.status,
        o.delivery_date_expected AS shipping_deadline
    FROM sales_orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.status IN ('confirmed','allocated','packed','shipped')
"""


PREVIOUS_PENDING_FULFILLMENT_BOARD_SQL = """
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
    alembic_op.execute("DROP VIEW IF EXISTS pending_fulfillment_board")
    alembic_op.execute(UPDATED_PENDING_FULFILLMENT_BOARD_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS pending_fulfillment_board")
    alembic_op.execute(PREVIOUS_PENDING_FULFILLMENT_BOARD_SQL)