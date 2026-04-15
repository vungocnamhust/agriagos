"""Add organization associations to preorders and sales orders.

Revision ID: 20260416_0023
Revises: 20260416_0022
Create Date: 2026-04-16 10:15:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0023"
down_revision = "20260416_0022"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column("preorders", sa.Column("organization_id", UUID, nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("organization_id", UUID, nullable=True))

    alembic_op.create_foreign_key(
        "fk_preorders_organization_id_organizations",
        "preorders",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )
    alembic_op.create_foreign_key(
        "fk_sales_orders_organization_id_organizations",
        "sales_orders",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )

    alembic_op.create_index("idx_preorders_organization_id", "preorders", ["organization_id"])
    alembic_op.create_index("idx_sales_orders_organization_id", "sales_orders", ["organization_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_sales_orders_organization_id", table_name="sales_orders")
    alembic_op.drop_index("idx_preorders_organization_id", table_name="preorders")

    alembic_op.drop_constraint(
        "fk_sales_orders_organization_id_organizations",
        "sales_orders",
        type_="foreignkey",
    )
    alembic_op.drop_constraint(
        "fk_preorders_organization_id_organizations",
        "preorders",
        type_="foreignkey",
    )

    alembic_op.drop_column("sales_orders", "organization_id")
    alembic_op.drop_column("preorders", "organization_id")