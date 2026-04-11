# pyright: reportAttributeAccessIssue=false
"""Add Phase 1 tenant_id placeholders required by coding guardrails.

Revision ID: 20260411_0007
Revises: 20260410_0006
Create Date: 2026-04-11 00:00:07
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from typing import Any


revision = "20260411_0007"
down_revision = "20260410_0006"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


TABLES = [
    "customers",
    "customer_preferences",
    "channel_identity_bindings",
    "product_skus",
    "plots",
    "crop_cycles",
    "preorders",
    "sales_orders",
    "sales_order_lines",
    "lots",
    "lot_evidence",
    "qc_reviews",
    "allocations",
    "inventory_movements",
    "external_mappings",
    "domain_events",
    "audit_logs",
    "idempotency_records",
]


def upgrade() -> None:
    for table_name in TABLES:
        alembic_op.add_column(
            table_name,
            sa.Column("tenant_id", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        )


def downgrade() -> None:
    for table_name in reversed(TABLES):
        alembic_op.drop_column(table_name, "tenant_id")