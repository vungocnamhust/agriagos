# pyright: reportAttributeAccessIssue=false
"""Add version column for optimistic locking to lots, sales_orders, preorders.

Revision ID: 20260411_0015
Revises: 20260411_0014
Create Date: 2026-04-11 22:00:00
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from typing import Any


revision = "20260411_0015"
down_revision = "20260411_0014"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    for table in ("lots", "sales_orders", "preorders"):
        alembic_op.add_column(
            table,
            sa.Column(
                "version",
                sa.Integer,
                nullable=False,
                server_default=sa.text("1"),
            ),
        )


def downgrade() -> None:
    for table in ("lots", "sales_orders", "preorders"):
        alembic_op.drop_column(table, "version")
