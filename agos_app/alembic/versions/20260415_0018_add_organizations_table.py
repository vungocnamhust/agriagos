# pyright: reportAttributeAccessIssue=false
"""Add organizations table.

Revision ID: 20260415_0018
Revises: 20260412_0017
Create Date: 2026-04-15 10:00:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260415_0018"
down_revision = "20260412_0017"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "organizations",
        sa.Column("organization_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        sa.Column("organization_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("organization_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("region", sa.Text()),
        sa.Column("locality_summary", sa.Text()),
        sa.Column("representative_name", sa.Text()),
        sa.Column("contact_phone", sa.Text()),
        sa.Column("contact_email", sa.Text()),
        sa.Column("short_description", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "organization_type IN ('household_producer','family_business','solo_founder','cooperative','startup_operator','other')",
            name="ck_organizations_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','closed')",
            name="ck_organizations_status",
        ),
        sa.UniqueConstraint("organization_code", name="uq_organizations_organization_code"),
    )
    alembic_op.create_index("idx_organizations_created_at", "organizations", ["created_at"])
    alembic_op.create_index("idx_organizations_status", "organizations", ["status"])


def downgrade() -> None:
    alembic_op.drop_index("idx_organizations_created_at", table_name="organizations")
    alembic_op.drop_index("idx_organizations_status", table_name="organizations")
    alembic_op.drop_table("organizations")