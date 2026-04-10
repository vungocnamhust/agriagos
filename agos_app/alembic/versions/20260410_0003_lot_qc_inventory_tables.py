# pyright: reportAttributeAccessIssue=false
"""Create lot, QC, and inventory tables.

Revision ID: 20260410_0003
Revises: 20260410_0002
Create Date: 2026-04-10 00:00:03
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Any


revision = "20260410_0003"
down_revision = "20260410_0002"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "lots",
        sa.Column("lot_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lot_code", sa.Text(), nullable=False),
        sa.Column("product_sku_id", UUID, nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_ref_id", sa.Text(), nullable=False),
        sa.Column("harvest_or_production_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("available_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("reserved_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("released_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("quality_note", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["product_sku_id"], ["product_skus.product_sku_id"]),
        sa.CheckConstraint("source_type IN ('crop_cycle','processing_batch','purchase_inbound')", name="ck_lots_source_type"),
        sa.CheckConstraint("actual_qty > 0", name="ck_lots_actual_qty"),
        sa.CheckConstraint("available_qty >= 0", name="ck_lots_available_qty"),
        sa.CheckConstraint("reserved_qty >= 0", name="ck_lots_reserved_qty"),
        sa.CheckConstraint("released_qty >= 0", name="ck_lots_released_qty"),
        sa.CheckConstraint("released_qty <= actual_qty", name="ck_lots_released_le_actual"),
        sa.CheckConstraint(
            "status IN ('draft','harvested','qc_pending','released','blocked','depleted','closed')",
            name="ck_lots_status",
        ),
        sa.UniqueConstraint("lot_code", name="uq_lots_lot_code"),
    )

    alembic_op.create_table(
        "lot_evidence",
        sa.Column("lot_evidence_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lot_id", UUID, nullable=False),
        sa.Column("evidence_type", sa.Text(), nullable=False),
        sa.Column("object_storage_key", sa.Text()),
        sa.Column("text_value", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_id", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.lot_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "evidence_type IN ('photo','video','checklist','note','document','measurement')",
            name="ck_lot_evidence_type",
        ),
        sa.CheckConstraint("status IN ('active','rejected')", name="ck_lot_evidence_status"),
        sa.CheckConstraint(
            "object_storage_key IS NOT NULL OR text_value IS NOT NULL",
            name="ck_lot_evidence_payload_present",
        ),
    )

    alembic_op.create_table(
        "qc_reviews",
        sa.Column("qc_review_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lot_id", UUID, nullable=False),
        sa.Column("checklist_version", sa.Text(), nullable=False),
        sa.Column("result", sa.Text(), nullable=False),
        sa.Column("reviewer_id", sa.Text()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.lot_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "result IN ('pending','passed','failed','needs_more_evidence')",
            name="ck_qc_reviews_result",
        ),
    )

    alembic_op.create_table(
        "allocations",
        sa.Column("allocation_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_line_id", UUID, nullable=False),
        sa.Column("lot_id", UUID, nullable=False),
        sa.Column("allocated_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("allocated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["order_line_id"], ["sales_order_lines.order_line_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.lot_id"]),
        sa.CheckConstraint("allocated_qty > 0", name="ck_allocations_allocated_qty"),
        sa.CheckConstraint("status IN ('active','released','consumed','cancelled')", name="ck_allocations_status"),
    )

    alembic_op.create_table(
        "inventory_movements",
        sa.Column("inventory_movement_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lot_id", UUID, nullable=False),
        sa.Column("movement_type", sa.Text(), nullable=False),
        sa.Column("qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("related_order_id", UUID),
        sa.Column("related_order_line_id", UUID),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lot_id"], ["lots.lot_id"]),
        sa.ForeignKeyConstraint(["related_order_id"], ["sales_orders.order_id"]),
        sa.ForeignKeyConstraint(["related_order_line_id"], ["sales_order_lines.order_line_id"]),
        sa.CheckConstraint(
            "movement_type IN ('release','reserve','release_reservation','consume','adjustment','discard','return')",
            name="ck_inventory_movements_type",
        ),
        sa.CheckConstraint("qty > 0", name="ck_inventory_movements_qty"),
    )


def downgrade() -> None:
    alembic_op.drop_table("inventory_movements")
    alembic_op.drop_table("allocations")
    alembic_op.drop_table("qc_reviews")
    alembic_op.drop_table("lot_evidence")
    alembic_op.drop_table("lots")