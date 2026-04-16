# pyright: reportAttributeAccessIssue=false
"""Add project contribution events table.

Revision ID: 20260416_0029
Revises: 20260416_0028
Create Date: 2026-04-16 19:10:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0029"
down_revision = "20260416_0028"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "project_contribution_events",
        sa.Column("project_contribution_event_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("project_assignment_id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", UUID, nullable=False),
        sa.Column("contribution_type", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("estimated_value", sa.Numeric(18, 2)),
        sa.Column("currency", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("confirmed_by", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_proj_contrib_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_assignment_id"], ["project_assignments.project_assignment_id"], name="fk_proj_contrib_assignment", ondelete="CASCADE"),
        sa.CheckConstraint("status IN ('proposed','confirmed','rejected')", name="ck_proj_contrib_status"),
    )
    alembic_op.create_index("idx_proj_contrib_scope", "project_contribution_events", ["project_scope_id"])
    alembic_op.create_index("idx_proj_contrib_assignment", "project_contribution_events", ["project_assignment_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_proj_contrib_assignment", table_name="project_contribution_events")
    alembic_op.drop_index("idx_proj_contrib_scope", table_name="project_contribution_events")
    alembic_op.drop_table("project_contribution_events")