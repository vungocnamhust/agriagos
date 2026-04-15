# pyright: reportAttributeAccessIssue=false
"""Add project scopes table.

Revision ID: 20260416_0026
Revises: 20260416_0025
Create Date: 2026-04-16 16:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0026"
down_revision = "20260416_0025"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "project_scopes",
        sa.Column("project_scope_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("project_scope_code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("project_scope_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("season_year", sa.Text()),
        sa.Column("owner_actor_id", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("parent_project_scope_id", UUID),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_project_scopes_organization_id_organizations"),
        sa.ForeignKeyConstraint(["parent_project_scope_id"], ["project_scopes.project_scope_id"], name="fk_project_scopes_parent_project_scope_id_project_scopes"),
        sa.CheckConstraint(
            "project_scope_type IN ('value_stream','product_line','household_livelihood','experience','campaign','umbrella_program','shared_service')",
            name="ck_project_scopes_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','closed','archived')",
            name="ck_project_scopes_status",
        ),
        sa.UniqueConstraint("project_scope_code", name="uq_project_scopes_project_scope_code"),
    )
    alembic_op.create_index("idx_project_scopes_created_at", "project_scopes", ["created_at"])
    alembic_op.create_index("idx_project_scopes_status", "project_scopes", ["status"])
    alembic_op.create_index("idx_project_scopes_organization_id", "project_scopes", ["organization_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_project_scopes_organization_id", table_name="project_scopes")
    alembic_op.drop_index("idx_project_scopes_status", table_name="project_scopes")
    alembic_op.drop_index("idx_project_scopes_created_at", table_name="project_scopes")
    alembic_op.drop_table("project_scopes")