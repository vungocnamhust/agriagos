"""Add organization associations to plots and crop cycles.

Revision ID: 20260415_0019
Revises: 20260415_0018
Create Date: 2026-04-15 12:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260415_0019"
down_revision = "20260415_0018"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column("plots", sa.Column("organization_id", UUID, nullable=True))
    alembic_op.add_column("crop_cycles", sa.Column("organization_id", UUID, nullable=True))

    alembic_op.create_foreign_key(
        "fk_plots_organization_id_organizations",
        "plots",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )
    alembic_op.create_foreign_key(
        "fk_crop_cycles_organization_id_organizations",
        "crop_cycles",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )

    alembic_op.create_index("idx_plots_organization_id", "plots", ["organization_id"])
    alembic_op.create_index("idx_crop_cycles_organization_id", "crop_cycles", ["organization_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_crop_cycles_organization_id", table_name="crop_cycles")
    alembic_op.drop_index("idx_plots_organization_id", table_name="plots")

    alembic_op.drop_constraint(
        "fk_crop_cycles_organization_id_organizations",
        "crop_cycles",
        type_="foreignkey",
    )
    alembic_op.drop_constraint(
        "fk_plots_organization_id_organizations",
        "plots",
        type_="foreignkey",
    )

    alembic_op.drop_column("crop_cycles", "organization_id")
    alembic_op.drop_column("plots", "organization_id")