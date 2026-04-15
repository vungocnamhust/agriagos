"""Add organization association to lots and available lots board.

Revision ID: 20260416_0021
Revises: 20260415_0020
Create Date: 2026-04-16 09:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0021"
down_revision = "20260415_0020"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
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
    alembic_op.add_column("lots", sa.Column("organization_id", UUID, nullable=True))
    alembic_op.create_foreign_key(
        "fk_lots_organization_id_organizations",
        "lots",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )
    alembic_op.create_index("idx_lots_organization_id", "lots", ["organization_id"])

    alembic_op.execute("DROP VIEW IF EXISTS available_lots_board")
    alembic_op.execute(UPDATED_AVAILABLE_LOTS_BOARD_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS available_lots_board")
    alembic_op.execute(PREVIOUS_AVAILABLE_LOTS_BOARD_SQL)

    alembic_op.drop_index("idx_lots_organization_id", table_name="lots")
    alembic_op.drop_constraint(
        "fk_lots_organization_id_organizations",
        "lots",
        type_="foreignkey",
    )
    alembic_op.drop_column("lots", "organization_id")