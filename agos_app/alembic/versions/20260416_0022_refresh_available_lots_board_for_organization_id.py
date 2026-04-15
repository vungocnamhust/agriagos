"""Refresh available lots board for organization id propagation.

Revision ID: 20260416_0022
Revises: 20260416_0021
Create Date: 2026-04-16 09:45:00
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260416_0022"
down_revision = "20260416_0021"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


UPDATED_AVAILABLE_LOTS_BOARD_SQL = """
    CREATE VIEW available_lots_board AS
    SELECT
        l.lot_id,
        l.lot_code,
        l.organization_id,
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
      AND l.available_qty > 0
"""


PREVIOUS_AVAILABLE_LOTS_BOARD_SQL = """
    CREATE VIEW available_lots_board AS
    SELECT
        l.lot_id,
        l.lot_code,
        l.organization_id,
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


def upgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS available_lots_board")
    alembic_op.execute(UPDATED_AVAILABLE_LOTS_BOARD_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS available_lots_board")
    alembic_op.execute(PREVIOUS_AVAILABLE_LOTS_BOARD_SQL)