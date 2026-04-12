# pyright: reportAttributeAccessIssue=false
"""Add failure_reason snapshot column to sales_orders.

Revision ID: 20260412_0017
Revises: 20260412_0016
Create Date: 2026-04-12 13:10:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa


revision = "20260412_0017"
down_revision = "20260412_0016"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column("sales_orders", sa.Column("failure_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    alembic_op.drop_column("sales_orders", "failure_reason")