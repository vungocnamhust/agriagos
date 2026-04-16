"""Repair external_mappings organization_id type and foreign key.

Revision ID: 20260416_0030
Revises: 20260416_0029
Create Date: 2026-04-16 18:45:00
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260416_0030"
down_revision = "20260416_0029"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.execute("DROP INDEX IF EXISTS idx_external_mappings_organization_id")
    alembic_op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'external_mappings'
                  AND column_name = 'organization_id'
                  AND udt_name <> 'uuid'
            ) THEN
                ALTER TABLE external_mappings
                ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid;
            END IF;
        END
        $$;
        """
    )
    alembic_op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_external_mappings_organization_id_organizations'
            ) THEN
                ALTER TABLE external_mappings
                ADD CONSTRAINT fk_external_mappings_organization_id_organizations
                FOREIGN KEY (organization_id)
                REFERENCES organizations (organization_id);
            END IF;
        END
        $$;
        """
    )
    alembic_op.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_mappings_organization_id ON external_mappings (organization_id)"
    )


def downgrade() -> None:
    alembic_op.execute(
        "ALTER TABLE external_mappings DROP CONSTRAINT IF EXISTS fk_external_mappings_organization_id_organizations"
    )
    alembic_op.execute("DROP INDEX IF EXISTS idx_external_mappings_organization_id")
    alembic_op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'external_mappings'
                  AND column_name = 'organization_id'
                  AND udt_name = 'uuid'
            ) THEN
                ALTER TABLE external_mappings
                ALTER COLUMN organization_id TYPE text USING organization_id::text;
            END IF;
        END
        $$;
        """
    )
    alembic_op.execute(
        "CREATE INDEX IF NOT EXISTS idx_external_mappings_organization_id ON external_mappings (organization_id)"
    )