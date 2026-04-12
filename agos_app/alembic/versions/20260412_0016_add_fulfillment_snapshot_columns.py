# pyright: reportAttributeAccessIssue=false
"""Add fulfillment snapshot columns to sales_orders.

Revision ID: 20260412_0016
Revises: 20260411_0015
Create Date: 2026-04-12 11:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa


revision = "20260412_0016"
down_revision = "20260411_0015"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column("sales_orders", sa.Column("carrier", sa.Text(), nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("tracking_ref", sa.Text(), nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("proof_ref", sa.Text(), nullable=True))
    alembic_op.add_column("sales_orders", sa.Column("delivery_note", sa.Text(), nullable=True))


def downgrade() -> None:
    alembic_op.drop_column("sales_orders", "delivery_note")
    alembic_op.drop_column("sales_orders", "proof_ref")
    alembic_op.drop_column("sales_orders", "delivered_at")
    alembic_op.drop_column("sales_orders", "shipped_at")
    alembic_op.drop_column("sales_orders", "tracking_ref")
    alembic_op.drop_column("sales_orders", "carrier")