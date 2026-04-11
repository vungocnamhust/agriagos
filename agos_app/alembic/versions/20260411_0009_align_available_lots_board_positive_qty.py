# pyright: reportAttributeAccessIssue=false
"""Align available lots board with positive-quantity operational semantics.

Revision ID: 20260411_0009
Revises: 20260411_0008
Create Date: 2026-04-11 00:00:09
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from typing import Any


revision = "20260411_0009"
down_revision = "20260411_0008"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


AVAILABLE_LOTS_BOARD_SQL = """
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
      AND l.available_qty > 0
"""


def upgrade() -> None:
    bind = alembic_op.get_bind()
    zero_qty_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
            FROM lots
            WHERE status = 'released'
              AND available_qty <= 0
            """
        )
    ).scalar_one()
    if zero_qty_count:
        print(
            "[migration 20260411_0009] WARNING: found "
            f"{zero_qty_count} released lots with non-positive available_qty; "
            "they will disappear from available_lots_board after this upgrade."
        )
    alembic_op.execute(AVAILABLE_LOTS_BOARD_SQL)


def downgrade() -> None:
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