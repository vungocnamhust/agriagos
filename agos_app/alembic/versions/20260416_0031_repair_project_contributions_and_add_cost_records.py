"""Repair contribution table state and add project cost records.

Revision ID: 20260416_0031
Revises: 20260416_0030
Create Date: 2026-04-16 21:30:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0031"
down_revision = "20260416_0030"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def _table_exists(table_name: str) -> bool:
    bind = alembic_op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def _index_names(table_name: str) -> set[str]:
    bind = alembic_op.get_bind()
    inspector = sa.inspect(bind)
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    if not _table_exists("project_contribution_events"):
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

    contribution_indexes = _index_names("project_contribution_events")
    if "idx_proj_contrib_scope" not in contribution_indexes:
        alembic_op.create_index("idx_proj_contrib_scope", "project_contribution_events", ["project_scope_id"])
    if "idx_proj_contrib_assignment" not in contribution_indexes:
        alembic_op.create_index("idx_proj_contrib_assignment", "project_contribution_events", ["project_assignment_id"])

    if _table_exists("project_cost_records"):
        return

    alembic_op.create_table(
        "project_cost_records",
        sa.Column("cost_record_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_scope_id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=False),
        sa.Column("cost_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("recognized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_object_type", sa.Text(), nullable=False),
        sa.Column("source_object_id", UUID, nullable=False),
        sa.Column("attribution_policy", sa.Text(), nullable=False),
        sa.Column("metadata_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_proj_cost_scope", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_proj_cost_org"),
        sa.CheckConstraint("cost_type IN ('labor_payout')", name="ck_proj_cost_type"),
        sa.CheckConstraint("source_object_type IN ('project_contribution_event')", name="ck_proj_cost_source_type"),
        sa.CheckConstraint("attribution_policy IN ('direct_source_link')", name="ck_proj_cost_attr_policy"),
    )
    alembic_op.create_index("idx_proj_cost_scope", "project_cost_records", ["project_scope_id"])
    alembic_op.create_index("idx_proj_cost_recognized_at", "project_cost_records", ["recognized_at"])
    alembic_op.create_index("idx_proj_cost_source", "project_cost_records", ["source_object_type", "source_object_id"])


def downgrade() -> None:
    if _table_exists("project_cost_records"):
        index_names = _index_names("project_cost_records")
        if "idx_proj_cost_source" in index_names:
            alembic_op.drop_index("idx_proj_cost_source", table_name="project_cost_records")
        if "idx_proj_cost_recognized_at" in index_names:
            alembic_op.drop_index("idx_proj_cost_recognized_at", table_name="project_cost_records")
        if "idx_proj_cost_scope" in index_names:
            alembic_op.drop_index("idx_proj_cost_scope", table_name="project_cost_records")
        alembic_op.drop_table("project_cost_records")