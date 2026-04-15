"""Add organization_id to external mappings.

This file restores revision ``20260416_0026`` after the original source file
was removed. The filename stays distinct to avoid filesystem collisions, while
the revision id remains ``20260416_0026`` so downstream migrations keep a
stable graph.

Revision ID: 20260416_0026
Revises: 20260416_0025
Create Date: 2026-04-16 18:20:00
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
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.add_column(
        "external_mappings",
        sa.Column("organization_id", UUID, nullable=True),
    )
    alembic_op.create_foreign_key(
        "fk_external_mappings_organization_id_organizations",
        "external_mappings",
        "organizations",
        ["organization_id"],
        ["organization_id"],
    )
    alembic_op.create_index(
        "idx_external_mappings_organization_id",
        "external_mappings",
        ["organization_id"],
    )


def downgrade() -> None:
    alembic_op.drop_index("idx_external_mappings_organization_id", table_name="external_mappings")
    alembic_op.drop_constraint(
        "fk_external_mappings_organization_id_organizations",
        "external_mappings",
        type_="foreignkey",
    )
    alembic_op.drop_column("external_mappings", "organization_id")
