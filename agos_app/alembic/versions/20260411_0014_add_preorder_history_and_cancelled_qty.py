# pyright: reportAttributeAccessIssue=false
"""Add preorder cancelled qty and adjustment history.

Revision ID: 20260411_0014
Revises: 20260411_0013
Create Date: 2026-04-11 21:40:00
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Any


revision = "20260411_0014"
down_revision = "20260411_0013"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column(
        "preorders",
        sa.Column("cancelled_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
    )
    alembic_op.create_check_constraint(
        "ck_preorders_cancelled_qty",
        "preorders",
        "cancelled_qty >= 0",
    )
    alembic_op.create_check_constraint(
        "ck_preorders_total_le_committed",
        "preorders",
        "allocated_qty + delivered_qty + cancelled_qty <= committed_qty",
    )
    alembic_op.execute(
        """
        UPDATE preorders
        SET remaining_qty = GREATEST(0, committed_qty - allocated_qty - delivered_qty - cancelled_qty)
        """
    )

    alembic_op.create_table(
        "preorder_adjustments",
        sa.Column("adjustment_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preorder_id", UUID, nullable=False),
        sa.Column("old_committed_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("new_committed_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text()),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["preorder_id"], ["preorders.preorder_id"], ondelete="CASCADE"),
        sa.CheckConstraint("old_committed_qty > 0", name="ck_preorder_adjustments_old_committed_qty"),
        sa.CheckConstraint("new_committed_qty > 0", name="ck_preorder_adjustments_new_committed_qty"),
    )
    alembic_op.create_index(
        "ix_preorder_adjustments_preorder_id_changed_at",
        "preorder_adjustments",
        ["preorder_id", "changed_at"],
        unique=False,
    )


def downgrade() -> None:
    alembic_op.drop_index("ix_preorder_adjustments_preorder_id_changed_at", table_name="preorder_adjustments")
    alembic_op.drop_table("preorder_adjustments")
    alembic_op.drop_constraint("ck_preorders_total_le_committed", "preorders", type_="check")
    alembic_op.drop_constraint("ck_preorders_cancelled_qty", "preorders", type_="check")
    alembic_op.drop_column("preorders", "cancelled_qty")