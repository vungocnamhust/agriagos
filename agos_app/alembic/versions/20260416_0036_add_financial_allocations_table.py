"""Add financial allocations table.

Revision ID: 20260416_0036
Revises: 20260416_0035
Create Date: 2026-04-17 03:00:00
"""

from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0036"
down_revision = "20260416_0035"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "financial_allocations",
        sa.Column("financial_allocation_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("source_record_type", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=False),
        sa.Column("allocation_basis", sa.Text(), nullable=False),
        sa.Column("allocation_weight", sa.Numeric(5, 4), nullable=False, server_default=sa.text("1.0")),
        sa.Column("allocated_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_financial_allocations_scope"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_financial_allocations_org"),
        sa.UniqueConstraint(
            "source_record_type",
            "source_record_id",
            name="uq_financial_allocations_source",
        ),
        sa.CheckConstraint("source_record_type IN ('cost_record')", name="ck_financial_allocations_source_type"),
        sa.CheckConstraint("allocation_basis IN ('manual_full')", name="ck_financial_allocations_basis"),
        sa.CheckConstraint("allocation_weight > 0 AND allocation_weight <= 1", name="ck_financial_allocations_weight"),
        sa.CheckConstraint("allocated_amount > 0", name="ck_financial_allocations_amount"),
    )
    alembic_op.create_index(
        "idx_financial_allocations_scope_created",
        "financial_allocations",
        ["project_scope_id", sa.text("created_at DESC")],
    )
    alembic_op.create_index(
        "idx_financial_allocations_source",
        "financial_allocations",
        ["source_record_type", "source_record_id"],
    )


def downgrade() -> None:
    alembic_op.drop_index("idx_financial_allocations_source", table_name="financial_allocations")
    alembic_op.drop_index("idx_financial_allocations_scope_created", table_name="financial_allocations")
    alembic_op.drop_table("financial_allocations")