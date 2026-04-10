# pyright: reportAttributeAccessIssue=false
"""Create Phase 1 core domain tables.

Revision ID: 20260410_0002
Revises: 20260410_0001
Create Date: 2026-04-10 00:00:02
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Any


revision = "20260410_0002"
down_revision = "20260410_0001"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "customers",
        sa.Column("customer_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_code", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("phone", sa.Text(), nullable=False),
        sa.Column("channel_source", sa.Text()),
        sa.Column("default_address", sa.Text()),
        sa.Column("district", sa.Text()),
        sa.Column("province", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("tags", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("notes", sa.Text()),
        sa.Column("last_order_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','inactive','blocked')", name="ck_customers_status"),
        sa.UniqueConstraint("customer_code", name="uq_customers_customer_code"),
        sa.UniqueConstraint("phone", name="uq_customers_phone"),
    )

    alembic_op.create_table(
        "customer_preferences",
        sa.Column("preference_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("preference_type", sa.Text(), nullable=False),
        sa.Column("preference_value", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'human'")),
        sa.Column("confidence_level", sa.Numeric(4, 3), nullable=False, server_default=sa.text("1.000")),
        sa.Column("confirmed_by", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.CheckConstraint("source IN ('human','integration','ai_suggestion')", name="ck_customer_preferences_source"),
        sa.CheckConstraint("confidence_level >= 0 AND confidence_level <= 1", name="ck_customer_preferences_confidence"),
    )

    alembic_op.create_table(
        "channel_identity_bindings",
        sa.Column("binding_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("channel_value", sa.Text(), nullable=False),
        sa.Column("customer_id", UUID),
        sa.Column("confidence_level", sa.Numeric(4, 3), nullable=False, server_default=sa.text("1.000")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.CheckConstraint("channel_type IN ('phone','zalo','facebook','email')", name="ck_channel_identity_bindings_type"),
        sa.CheckConstraint("status IN ('active','candidate','rejected')", name="ck_channel_identity_bindings_status"),
        sa.CheckConstraint("confidence_level >= 0 AND confidence_level <= 1", name="ck_channel_identity_bindings_confidence"),
        sa.UniqueConstraint("channel_type", "channel_value", name="uq_channel_identity_bindings_channel"),
    )

    alembic_op.create_table(
        "product_skus",
        sa.Column("product_sku_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sku_code", sa.Text(), nullable=False),
        sa.Column("sku_name", sa.Text(), nullable=False),
        sa.Column("category", sa.Text()),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("pack_size", sa.Text()),
        sa.Column("default_price", sa.Numeric(18, 2)),
        sa.Column("is_preorder_supported", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_product_skus_status"),
        sa.UniqueConstraint("sku_code", name="uq_product_skus_sku_code"),
    )

    alembic_op.create_table(
        "plots",
        sa.Column("plot_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plot_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("location_text", sa.Text()),
        sa.Column("area_value", sa.Numeric(18, 3), nullable=False),
        sa.Column("area_unit", sa.Text(), nullable=False),
        sa.Column("owner_name", sa.Text()),
        sa.Column("manager_user_id", sa.Text()),
        sa.Column("geo_lat", sa.Numeric(10, 7)),
        sa.Column("geo_lng", sa.Numeric(10, 7)),
        sa.Column("soil_note", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("status IN ('active','inactive')", name="ck_plots_status"),
        sa.UniqueConstraint("plot_code", name="uq_plots_plot_code"),
    )

    alembic_op.create_table(
        "crop_cycles",
        sa.Column("crop_cycle_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("plot_id", UUID, nullable=False),
        sa.Column("crop_name", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("growth_stage", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("expected_harvest_from", sa.DateTime(timezone=True)),
        sa.Column("expected_harvest_to", sa.DateTime(timezone=True)),
        sa.Column("estimated_yield_qty", sa.Numeric(18, 3)),
        sa.Column("actual_yield_qty", sa.Numeric(18, 3)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["plot_id"], ["plots.plot_id"]),
        sa.CheckConstraint(
            "growth_stage IN ('seeded','growing','flowering_or_maturing','harvest_window','harvested')",
            name="ck_crop_cycles_growth_stage",
        ),
        sa.CheckConstraint(
            "status IN ('planned','active','near_harvest','harvested','closed','cancelled')",
            name="ck_crop_cycles_status",
        ),
    )

    alembic_op.create_table(
        "preorders",
        sa.Column("preorder_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("preorder_code", sa.Text(), nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("product_sku_id", UUID, nullable=False),
        sa.Column("committed_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("allocated_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("delivered_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("delivery_cadence", sa.Text()),
        sa.Column("deposit_amount", sa.Numeric(18, 2)),
        sa.Column("notes", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("start_date", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.ForeignKeyConstraint(["product_sku_id"], ["product_skus.product_sku_id"]),
        sa.CheckConstraint("committed_qty > 0", name="ck_preorders_committed_qty"),
        sa.CheckConstraint("allocated_qty >= 0", name="ck_preorders_allocated_qty"),
        sa.CheckConstraint("delivered_qty >= 0", name="ck_preorders_delivered_qty"),
        sa.CheckConstraint("remaining_qty >= 0", name="ck_preorders_remaining_qty"),
        sa.CheckConstraint("allocated_qty <= committed_qty", name="ck_preorders_allocated_le_committed"),
        sa.CheckConstraint("delivered_qty <= committed_qty", name="ck_preorders_delivered_le_committed"),
        sa.CheckConstraint("status IN ('draft','confirmed','active','completed','cancelled')", name="ck_preorders_status"),
        sa.UniqueConstraint("preorder_code", name="uq_preorders_preorder_code"),
    )

    alembic_op.create_table(
        "sales_orders",
        sa.Column("order_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_code", sa.Text(), nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivery_date_expected", sa.DateTime(timezone=True)),
        sa.Column("shipping_address", sa.Text()),
        sa.Column("payment_intent", sa.Text()),
        sa.Column("note", sa.Text()),
        sa.Column("created_by", sa.Text()),
        sa.Column("source_preorder_flag", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("payment_status", sa.Text(), nullable=False, server_default=sa.text("'unpaid'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"]),
        sa.CheckConstraint("channel IN ('web','admin','zalo','facebook','phone')", name="ck_sales_orders_channel"),
        sa.CheckConstraint(
            "status IN ('draft','confirmed','allocated','partially_allocated','packed','partially_packed','shipped','delivered','partially_delivered','cancel_requested','cancelled','failed')",
            name="ck_sales_orders_status",
        ),
        sa.CheckConstraint(
            "payment_status IN ('unpaid','partially_paid','paid','refunded','writeoff')",
            name="ck_sales_orders_payment_status",
        ),
        sa.UniqueConstraint("order_code", name="uq_sales_orders_order_code"),
    )

    alembic_op.create_table(
        "sales_order_lines",
        sa.Column("order_line_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("order_id", UUID, nullable=False),
        sa.Column("product_sku_id", UUID, nullable=False),
        sa.Column("ordered_qty", sa.Numeric(18, 3), nullable=False),
        sa.Column("allocated_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("packed_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("delivered_qty", sa.Numeric(18, 3), nullable=False, server_default=sa.text("0")),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("source_preorder_id", UUID),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.ForeignKeyConstraint(["order_id"], ["sales_orders.order_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_sku_id"], ["product_skus.product_sku_id"]),
        sa.ForeignKeyConstraint(["source_preorder_id"], ["preorders.preorder_id"]),
        sa.CheckConstraint("ordered_qty > 0", name="ck_sales_order_lines_ordered_qty"),
        sa.CheckConstraint("allocated_qty >= 0", name="ck_sales_order_lines_allocated_qty"),
        sa.CheckConstraint("packed_qty >= 0", name="ck_sales_order_lines_packed_qty"),
        sa.CheckConstraint("delivered_qty >= 0", name="ck_sales_order_lines_delivered_qty"),
        sa.CheckConstraint("allocated_qty <= ordered_qty", name="ck_sales_order_lines_allocated_le_ordered"),
        sa.CheckConstraint("packed_qty <= ordered_qty", name="ck_sales_order_lines_packed_le_ordered"),
        sa.CheckConstraint("delivered_qty <= ordered_qty", name="ck_sales_order_lines_delivered_le_ordered"),
        sa.CheckConstraint("status IN ('open','allocated','packed','delivered','cancelled')", name="ck_sales_order_lines_status"),
    )


def downgrade() -> None:
    alembic_op.drop_table("sales_order_lines")
    alembic_op.drop_table("sales_orders")
    alembic_op.drop_table("preorders")
    alembic_op.drop_table("crop_cycles")
    alembic_op.drop_table("plots")
    alembic_op.drop_table("product_skus")
    alembic_op.drop_table("channel_identity_bindings")
    alembic_op.drop_table("customer_preferences")
    alembic_op.drop_table("customers")