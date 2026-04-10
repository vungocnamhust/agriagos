# pyright: reportAttributeAccessIssue=false
"""Create eventing, audit, and mapping tables.

Revision ID: 20260410_0004
Revises: 20260410_0003
Create Date: 2026-04-10 00:00:04
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Any


revision = "20260410_0004"
down_revision = "20260410_0003"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.create_table(
        "external_mappings",
        sa.Column("external_mapping_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_system", sa.Text(), nullable=False),
        sa.Column("external_object_type", sa.Text(), nullable=False),
        sa.Column("external_object_id", sa.Text(), nullable=False),
        sa.Column("internal_object_type", sa.Text(), nullable=False),
        sa.Column("internal_object_id", sa.Text(), nullable=False),
        sa.Column("sync_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.CheckConstraint("sync_status IN ('pending','synced','failed','needs_review')", name="ck_external_mappings_sync_status"),
        sa.UniqueConstraint(
            "external_system",
            "external_object_type",
            "external_object_id",
            name="uq_external_mappings_external_ref",
        ),
    )

    alembic_op.create_table(
        "domain_events",
        sa.Column("event_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_name", sa.Text(), nullable=False),
        sa.Column("event_version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("aggregate_type", sa.Text(), nullable=False),
        sa.Column("aggregate_id", sa.Text(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text()),
        sa.Column("correlation_id", sa.Text()),
        sa.Column("causation_id", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("source", sa.Text(), nullable=False, server_default=sa.text("'core'")),
        sa.Column("payload", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("actor_type IN ('user','system','agent','integration')", name="ck_domain_events_actor_type"),
        sa.CheckConstraint("source IN ('core','integration','system_job','agent')", name="ck_domain_events_source"),
    )

    alembic_op.create_table(
        "audit_logs",
        sa.Column("audit_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_id", sa.Text()),
        sa.Column("actor_role", sa.Text()),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.Text(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text()),
        sa.Column("before_snapshot", JSONB),
        sa.Column("after_snapshot", JSONB),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("correlation_id", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("decision IN ('allowed','denied','escalated','failed')", name="ck_audit_logs_decision"),
    )

    alembic_op.create_table(
        "idempotency_records",
        sa.Column("idempotency_key", sa.Text(), primary_key=True),
        sa.Column("operation_name", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("response_snapshot", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    alembic_op.drop_table("idempotency_records")
    alembic_op.drop_table("audit_logs")
    alembic_op.drop_table("domain_events")
    alembic_op.drop_table("external_mappings")