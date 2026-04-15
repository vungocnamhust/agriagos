# pyright: reportAttributeAccessIssue=false
"""Add project assignments table.

Revision ID: 20260416_0027
Revises: 20260416_0026
Create Date: 2026-04-16 17:40:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0027"
down_revision = "20260416_0026"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "project_assignments",
        sa.Column("project_assignment_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", UUID, nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attribution_weight", sa.Numeric(6, 5)),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column("ended_reason", sa.Text()),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_project_assignments_project_scope_id_project_scopes", ondelete="CASCADE"),
        sa.CheckConstraint(
            "target_type IN ('plot','crop_cycle','lot','preorder','order')",
            name="ck_project_assignments_target_type",
        ),
        sa.CheckConstraint(
            "attribution_weight IS NULL OR (attribution_weight >= 0 AND attribution_weight <= 1)",
            name="ck_project_assignments_attribution_weight",
        ),
    )
    alembic_op.create_index("idx_project_assignments_project_scope_id", "project_assignments", ["project_scope_id"])
    alembic_op.create_index("idx_project_assignments_target", "project_assignments", ["target_type", "target_id"])


def downgrade() -> None:
    alembic_op.drop_index("idx_project_assignments_target", table_name="project_assignments")
    alembic_op.drop_index("idx_project_assignments_project_scope_id", table_name="project_assignments")
    alembic_op.drop_table("project_assignments")