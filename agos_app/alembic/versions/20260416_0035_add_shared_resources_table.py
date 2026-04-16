"""Add shared resources table.

Revision ID: 20260416_0035
Revises: 20260416_0034
Create Date: 2026-04-17 01:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0035"
down_revision = "20260416_0034"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "shared_resources",
        sa.Column("shared_resource_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("resource_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("capacity_value", sa.Numeric(18, 2), nullable=True),
        sa.Column("capacity_unit", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_shared_resource_org"),
        sa.UniqueConstraint("resource_code", name="uq_shared_resources_resource_code"),
        sa.CheckConstraint(
            "resource_type IN ('labor_pool','vehicle','drying_yard','warehouse','marketing_budget','content_asset','host_capacity','other')",
            name="ck_shared_resources_resource_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','inactive','retired')",
            name="ck_shared_resources_status",
        ),
    )
    alembic_op.create_index("idx_shared_resources_org_created", "shared_resources", ["organization_id", sa.text("created_at DESC")])


def downgrade() -> None:
    alembic_op.drop_index("idx_shared_resources_org_created", table_name="shared_resources")
    alembic_op.drop_table("shared_resources")