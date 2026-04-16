"""Add project revenue records.

Revision ID: 20260416_0034
Revises: 20260416_0033
Create Date: 2026-04-16 23:55:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0034"
down_revision = "20260416_0033"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "project_revenue_records",
        sa.Column("revenue_record_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("customer_id", UUID, nullable=False),
        sa.Column("revenue_type", sa.Text(), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_object_type", sa.Text(), nullable=False),
        sa.Column("source_object_id", UUID, nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_proj_rev_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_proj_rev_org"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.customer_id"], name="fk_proj_rev_customer"),
        sa.CheckConstraint("revenue_type IN ('delivered_order_sale')", name="ck_proj_rev_type"),
        sa.CheckConstraint("source_object_type IN ('order')", name="ck_proj_rev_source_type"),
        sa.UniqueConstraint("project_scope_id", "source_object_type", "source_object_id", name="uq_proj_rev_scope_source"),
    )
    alembic_op.create_index(
        "idx_proj_rev_scope_recognized",
        "project_revenue_records",
        [sa.text("project_scope_id"), sa.text("recognized_at DESC"), sa.text("revenue_record_id")],
    )
    alembic_op.create_index("idx_proj_rev_source", "project_revenue_records", ["source_object_type", "source_object_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_proj_rev_source", table_name="project_revenue_records")
    alembic_op.drop_index("idx_proj_rev_scope_recognized", table_name="project_revenue_records")
    alembic_op.drop_table("project_revenue_records")