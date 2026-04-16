"""Align project contribution actor columns to text ids.

This migration is defensive-only. The checked-in 0029/0031 migration path
already creates ``actor_id`` and ``confirmed_by`` as text columns, so upgrade
is a no-op on the standard chain. It exists to repair environments that created
the table with UUID actor columns outside the current migration history.

Downgrade note: rollback to UUID columns is only safe while
``actor_id`` and ``confirmed_by`` still contain UUID-compatible text values.
If non-UUID actor ids have been written after this migration, clean or remap
them before downgrade.

Revision ID: 20260416_0032
Revises: 20260416_0031
Create Date: 2026-04-16 22:00:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0032"
down_revision = "20260416_0031"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def _column_type_by_name(table_name: str) -> dict[str, Any]:
    bind = alembic_op.get_bind()
    inspector = sa.inspect(bind)
    return {column["name"]: column["type"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = alembic_op.get_bind()
    inspector = sa.inspect(bind)
    if "project_contribution_events" not in inspector.get_table_names():
        return

    column_types = _column_type_by_name("project_contribution_events")

    if isinstance(column_types.get("actor_id"), postgresql.UUID):
        alembic_op.alter_column(
            "project_contribution_events",
            "actor_id",
            existing_type=sa.dialects.postgresql.UUID(as_uuid=False),
            type_=sa.Text(),
            postgresql_using="actor_id::text",
        )
    if isinstance(column_types.get("confirmed_by"), postgresql.UUID):
        alembic_op.alter_column(
            "project_contribution_events",
            "confirmed_by",
            existing_type=sa.dialects.postgresql.UUID(as_uuid=False),
            type_=sa.Text(),
            postgresql_using="confirmed_by::text",
            existing_nullable=True,
        )


def downgrade() -> None:
    bind = alembic_op.get_bind()
    inspector = sa.inspect(bind)
    if "project_contribution_events" not in inspector.get_table_names():
        return

    column_types = _column_type_by_name("project_contribution_events")

    # Downgrade intentionally keeps the cast explicit so rollback fails fast if
    # text actor ids are no longer UUID-compatible.
    if isinstance(column_types.get("actor_id"), sa.Text):
        alembic_op.alter_column(
            "project_contribution_events",
            "actor_id",
            existing_type=sa.Text(),
            type_=sa.dialects.postgresql.UUID(as_uuid=False),
            postgresql_using="actor_id::uuid",
        )
    if isinstance(column_types.get("confirmed_by"), sa.Text):
        alembic_op.alter_column(
            "project_contribution_events",
            "confirmed_by",
            existing_type=sa.Text(),
            type_=sa.dialects.postgresql.UUID(as_uuid=False),
            postgresql_using="NULLIF(confirmed_by, '')::uuid",
            existing_nullable=True,
        )