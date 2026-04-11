# pyright: reportAttributeAccessIssue=false
"""Add unit snapshot column for lots.

Revision ID: 20260411_0013
Revises: 20260411_0012
Create Date: 2026-04-11 20:15:00
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from typing import Any


revision = "20260411_0013"
down_revision = "20260411_0012"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column(
        "lots",
        sa.Column("unit", sa.Text(), nullable=False, server_default=sa.text("'kg'")),
    )


def downgrade() -> None:
    alembic_op.drop_column("lots", "unit")