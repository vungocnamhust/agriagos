"""Add shared resource allocations table.

Revision ID: 20260416_0038
Revises: 20260416_0037
Create Date: 2026-04-17 05:00:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0038"
down_revision = "20260416_0037"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "shared_resource_allocations",
        sa.Column("allocation_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shared_resource_id", UUID, nullable=False),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("allocation_basis", sa.Text(), nullable=False),
        sa.Column("allocated_capacity", sa.Numeric(18, 2), nullable=False),
        sa.Column("released_capacity", sa.Numeric(18, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["shared_resource_id"], ["shared_resources.shared_resource_id"], name="fk_shared_resource_allocations_resource"),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_shared_resource_allocations_scope"),
        sa.CheckConstraint("allocated_capacity > 0", name="ck_shared_resource_allocations_allocated_capacity"),
        sa.CheckConstraint("released_capacity >= 0 AND released_capacity <= allocated_capacity", name="ck_shared_resource_allocations_released_capacity"),
        sa.CheckConstraint("status IN ('active','released')", name="ck_shared_resource_allocations_status"),
    )
    alembic_op.create_index(
        "idx_shared_resource_allocations_resource_status",
        "shared_resource_allocations",
        ["shared_resource_id", "status"],
    )
    alembic_op.create_index(
        "idx_shared_resource_allocations_scope_status",
        "shared_resource_allocations",
        ["project_scope_id", "status"],
    )


def downgrade() -> None:
    alembic_op.drop_index("idx_shared_resource_allocations_scope_status", table_name="shared_resource_allocations")
    alembic_op.drop_index("idx_shared_resource_allocations_resource_status", table_name="shared_resource_allocations")
    alembic_op.drop_table("shared_resource_allocations")