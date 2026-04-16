"""Add actor identity and affiliation tables.

Revision ID: 20260416_0039
Revises: 20260416_0038
Create Date: 2026-04-17 05:00:00
"""
from __future__ import annotations

import importlib
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260416_0039"
down_revision = "20260416_0038"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "actor_identities",
        sa.Column("actor_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        sa.Column("actor_code", sa.Text(), nullable=False),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("primary_phone", sa.Text(), nullable=True),
        sa.Column("primary_email", sa.Text(), nullable=True),
        sa.Column("external_mappings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("actor_code", name="uq_actor_identities_actor_code"),
        sa.CheckConstraint(
            "actor_type IN ('person','household','organization_actor','automation_principal')",
            name="ck_actor_identities_actor_type",
        ),
        sa.CheckConstraint(
            "status IN ('active','inactive')",
            name="ck_actor_identities_status",
        ),
    )
    alembic_op.create_index("idx_actor_identities_created", "actor_identities", [sa.text("created_at DESC")])

    alembic_op.create_table(
        "actor_affiliations",
        sa.Column("actor_affiliation_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", UUID, nullable=False),
        sa.Column("organization_id", UUID, nullable=True),
        sa.Column("project_scope_id", UUID, nullable=True),
        sa.Column("affiliation_kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["actor_id"], ["actor_identities.actor_id"], name="fk_actor_affiliations_actor"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.organization_id"], name="fk_actor_affiliations_org"),
        sa.ForeignKeyConstraint(["project_scope_id"], ["project_scopes.project_scope_id"], name="fk_actor_affiliations_project_scope"),
        sa.CheckConstraint(
            "affiliation_kind IN ('membership','stewardship','contractor','partner','observer')",
            name="ck_actor_affiliations_kind",
        ),
        sa.CheckConstraint(
            "status IN ('active','ended')",
            name="ck_actor_affiliations_status",
        ),
        sa.CheckConstraint(
            "organization_id IS NOT NULL OR project_scope_id IS NOT NULL",
            name="ck_actor_affiliations_scope_anchor",
        ),
    )
    alembic_op.create_index("idx_actor_affiliations_actor_effective", "actor_affiliations", ["actor_id", sa.text("effective_at DESC")])


def downgrade() -> None:
    alembic_op.drop_index("idx_actor_affiliations_actor_effective", table_name="actor_affiliations")
    alembic_op.drop_table("actor_affiliations")
    alembic_op.drop_index("idx_actor_identities_created", table_name="actor_identities")
    alembic_op.drop_table("actor_identities")