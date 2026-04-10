# pyright: reportAttributeAccessIssue=false
"""Create Phase 1 workflow indexes.

Revision ID: 20260410_0005
Revises: 20260410_0004
Create Date: 2026-04-10 00:00:05
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260410_0005"
down_revision = "20260410_0004"
branch_labels = None
depends_on = None

alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_index("idx_preorders_customer_id", "preorders", ["customer_id"])
    alembic_op.create_index("idx_preorders_product_sku_id", "preorders", ["product_sku_id"])
    alembic_op.create_index("idx_preorders_status", "preorders", ["status"])
    alembic_op.create_index("idx_sales_orders_customer_id", "sales_orders", ["customer_id"])
    alembic_op.create_index("idx_sales_orders_status", "sales_orders", ["status"])
    alembic_op.create_index("idx_sales_orders_delivery_date_expected", "sales_orders", ["delivery_date_expected"])
    alembic_op.create_index("idx_sales_order_lines_order_id", "sales_order_lines", ["order_id"])
    alembic_op.create_index("idx_crop_cycles_plot_id", "crop_cycles", ["plot_id"])
    alembic_op.create_index("idx_lots_product_sku_id", "lots", ["product_sku_id"])
    alembic_op.create_index("idx_lots_status", "lots", ["status"])
    alembic_op.create_index("idx_allocations_order_line_id", "allocations", ["order_line_id"])
    alembic_op.create_index("idx_allocations_lot_id", "allocations", ["lot_id"])
    alembic_op.create_index("idx_inventory_movements_lot_id", "inventory_movements", ["lot_id"])
    alembic_op.create_index("idx_lot_evidence_lot_id", "lot_evidence", ["lot_id"])
    alembic_op.create_index("idx_lot_evidence_lot_status_type", "lot_evidence", ["lot_id", "status", "evidence_type"])
    alembic_op.create_index("idx_qc_reviews_lot_id", "qc_reviews", ["lot_id"])
    alembic_op.create_index("idx_qc_reviews_lot_result_reviewed_at", "qc_reviews", ["lot_id", "result", "reviewed_at"])
    alembic_op.create_index("idx_domain_events_aggregate", "domain_events", ["aggregate_type", "aggregate_id"])
    alembic_op.create_index("idx_domain_events_correlation", "domain_events", ["correlation_id"])
    alembic_op.create_index("idx_domain_events_idempotency_key", "domain_events", ["idempotency_key"])
    alembic_op.create_index("idx_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    alembic_op.create_index("idx_audit_logs_correlation", "audit_logs", ["correlation_id"])
    alembic_op.create_index("idx_external_mappings_internal", "external_mappings", ["internal_object_type", "internal_object_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_external_mappings_internal", table_name="external_mappings")
    alembic_op.drop_index("idx_audit_logs_correlation", table_name="audit_logs")
    alembic_op.drop_index("idx_audit_logs_target", table_name="audit_logs")
    alembic_op.drop_index("idx_domain_events_idempotency_key", table_name="domain_events")
    alembic_op.drop_index("idx_domain_events_correlation", table_name="domain_events")
    alembic_op.drop_index("idx_domain_events_aggregate", table_name="domain_events")
    alembic_op.drop_index("idx_qc_reviews_lot_result_reviewed_at", table_name="qc_reviews")
    alembic_op.drop_index("idx_qc_reviews_lot_id", table_name="qc_reviews")
    alembic_op.drop_index("idx_lot_evidence_lot_status_type", table_name="lot_evidence")
    alembic_op.drop_index("idx_lot_evidence_lot_id", table_name="lot_evidence")
    alembic_op.drop_index("idx_inventory_movements_lot_id", table_name="inventory_movements")
    alembic_op.drop_index("idx_allocations_lot_id", table_name="allocations")
    alembic_op.drop_index("idx_allocations_order_line_id", table_name="allocations")
    alembic_op.drop_index("idx_lots_status", table_name="lots")
    alembic_op.drop_index("idx_lots_product_sku_id", table_name="lots")
    alembic_op.drop_index("idx_crop_cycles_plot_id", table_name="crop_cycles")
    alembic_op.drop_index("idx_sales_order_lines_order_id", table_name="sales_order_lines")
    alembic_op.drop_index("idx_sales_orders_delivery_date_expected", table_name="sales_orders")
    alembic_op.drop_index("idx_sales_orders_status", table_name="sales_orders")
    alembic_op.drop_index("idx_sales_orders_customer_id", table_name="sales_orders")
    alembic_op.drop_index("idx_preorders_status", table_name="preorders")
    alembic_op.drop_index("idx_preorders_product_sku_id", table_name="preorders")
    alembic_op.drop_index("idx_preorders_customer_id", table_name="preorders")