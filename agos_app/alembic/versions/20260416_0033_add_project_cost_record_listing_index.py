"""Strengthen project cost record listing index.

Deployment note: creating the composite index takes a write lock on
``project_cost_records`` in PostgreSQL. Run this migration in a low-traffic
window if the table has material write volume.

Revision ID: 20260416_0033
Revises: 20260416_0032
Create Date: 2026-04-16 23:20:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa


revision = "20260416_0033"
down_revision = "20260416_0032"
branch_labels = None
depends_on = None


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
    if not _table_exists("project_cost_records"):
        return

    index_names = _index_names("project_cost_records")
    if "idx_proj_cost_scope_recognized" not in index_names:
        alembic_op.execute(
            """
            CREATE INDEX idx_proj_cost_scope_recognized
            ON project_cost_records (project_scope_id, recognized_at DESC, cost_record_id)
            """
        )

    if "idx_proj_cost_recognized_at" in index_names:
        alembic_op.drop_index("idx_proj_cost_recognized_at", table_name="project_cost_records")


def downgrade() -> None:
    if not _table_exists("project_cost_records"):
        return

    index_names = _index_names("project_cost_records")
    if "idx_proj_cost_scope_recognized" in index_names:
        alembic_op.drop_index("idx_proj_cost_scope_recognized", table_name="project_cost_records")
    if "idx_proj_cost_scope" not in index_names:
        alembic_op.create_index("idx_proj_cost_scope", "project_cost_records", ["project_scope_id"])
    if "idx_proj_cost_recognized_at" not in index_names:
        alembic_op.create_index("idx_proj_cost_recognized_at", "project_cost_records", ["recognized_at"])