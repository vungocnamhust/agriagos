"""Extend financial allocations for weighted splits.

Revision ID: 20260416_0037
Revises: 20260416_0036
Create Date: 2026-04-17 04:00:00
"""

from __future__ import annotations

import importlib
from typing import Any


revision = "20260416_0037"
down_revision = "20260416_0036"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.execute(
        "ALTER TABLE financial_allocations DROP CONSTRAINT IF EXISTS uq_financial_allocations_source"
    )
    alembic_op.execute(
        "ALTER TABLE financial_allocations DROP CONSTRAINT IF EXISTS ck_financial_allocations_basis"
    )
    alembic_op.execute(
        "ALTER TABLE financial_allocations DROP CONSTRAINT IF EXISTS uq_financial_allocations_scope_source"
    )
    alembic_op.execute(
        "ALTER TABLE financial_allocations ADD CONSTRAINT uq_financial_allocations_scope_source UNIQUE (project_scope_id, source_record_type, source_record_id)"
    )
    alembic_op.execute(
        "ALTER TABLE financial_allocations DROP CONSTRAINT IF EXISTS ck_financial_allocations_basis"
    )
    alembic_op.create_check_constraint(
        "ck_financial_allocations_basis",
        "financial_allocations",
        "allocation_basis IN ('manual_full', 'manual_weighted')",
    )
    alembic_op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_financial_allocations_manual_full_source ON financial_allocations (source_record_type, source_record_id) WHERE allocation_basis = 'manual_full'"
    )


def downgrade() -> None:
    alembic_op.execute("DROP INDEX IF EXISTS idx_financial_allocations_manual_full_source")
    alembic_op.drop_constraint("uq_financial_allocations_scope_source", "financial_allocations", type_="unique")
    alembic_op.drop_constraint("ck_financial_allocations_basis", "financial_allocations", type_="check")
    alembic_op.create_unique_constraint(
        "uq_financial_allocations_source",
        "financial_allocations",
        ["source_record_type", "source_record_id"],
    )
    alembic_op.create_check_constraint(
        "ck_financial_allocations_basis",
        "financial_allocations",
        "allocation_basis IN ('manual_full')",
    )