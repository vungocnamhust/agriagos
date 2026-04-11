# pyright: reportAttributeAccessIssue=false
"""Add customer core foundation columns and duplicate candidate table.

Revision ID: 20260411_0012
Revises: 20260411_0011
Create Date: 2026-04-11 18:30:00
"""
from __future__ import annotations

import importlib
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from typing import Any


revision = "20260411_0012"
down_revision = "20260411_0011"
branch_labels = None
depends_on = None


UUID = postgresql.UUID(as_uuid=False)
JSONB = postgresql.JSONB(astext_type=sa.Text())
alembic_op: Any = importlib.import_module("alembic.op")


PHONE_NORMALIZATION_SQL = """
    CASE
        WHEN regexp_replace(phone, '\\D', '', 'g') LIKE '84%' AND length(regexp_replace(phone, '\\D', '', 'g')) > 9
            THEN '0' || substring(regexp_replace(phone, '\\D', '', 'g') from 3)
        ELSE regexp_replace(phone, '\\D', '', 'g')
    END
"""


def upgrade() -> None:
    alembic_op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    alembic_op.add_column("customers", sa.Column("phone_normalized", sa.Text(), nullable=True))
    alembic_op.execute(f"UPDATE customers SET phone_normalized = {PHONE_NORMALIZATION_SQL}")
    alembic_op.alter_column("customers", "phone_normalized", nullable=False)
    alembic_op.create_unique_constraint("uq_customers_phone_normalized", "customers", ["phone_normalized"])
    alembic_op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_full_name_trgm ON customers USING gin (lower(full_name) gin_trgm_ops)"
    )
    alembic_op.execute(
        "CREATE INDEX IF NOT EXISTS idx_customers_customer_code_trgm ON customers USING gin (lower(customer_code) gin_trgm_ops)"
    )

    alembic_op.add_column("customer_preferences", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True))
    alembic_op.execute("UPDATE customer_preferences SET confirmed_at = updated_at WHERE confirmed_by IS NOT NULL")

    alembic_op.create_table(
        "customer_duplicate_candidates",
        sa.Column("candidate_id", UUID, primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("primary_customer_id", UUID, nullable=False),
        sa.Column("suspected_customer_id", UUID, nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=False),
        sa.Column("match_score", sa.Numeric(5, 3), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'open'")),
        sa.Column("evidence_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("detected_by", sa.Text()),
        sa.Column("reviewed_by", sa.Text()),
        sa.Column("review_note", sa.Text()),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["primary_customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suspected_customer_id"], ["customers.customer_id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('open','reviewed_duplicate','reviewed_distinct','ignored')",
            name="ck_customer_duplicate_candidates_status",
        ),
        sa.CheckConstraint("match_score >= 0 AND match_score <= 1", name="ck_customer_duplicate_candidates_match_score"),
        sa.UniqueConstraint(
            "primary_customer_id",
            "suspected_customer_id",
            "match_reason",
            "status",
            name="uq_customer_duplicate_candidates_pair_status",
        ),
    )
    alembic_op.create_index(
        "idx_customer_duplicate_candidates_status_detected_at",
        "customer_duplicate_candidates",
        ["status", "detected_at"],
    )
    alembic_op.create_index(
        "idx_customer_duplicate_candidates_primary_customer_id",
        "customer_duplicate_candidates",
        ["primary_customer_id"],
    )
    alembic_op.create_index(
        "idx_customer_duplicate_candidates_suspected_customer_id",
        "customer_duplicate_candidates",
        ["suspected_customer_id"],
    )


def downgrade() -> None:
    alembic_op.execute("DROP INDEX IF EXISTS idx_customers_customer_code_trgm")
    alembic_op.execute("DROP INDEX IF EXISTS idx_customers_full_name_trgm")
    alembic_op.drop_index("idx_customer_duplicate_candidates_suspected_customer_id", table_name="customer_duplicate_candidates")
    alembic_op.drop_index("idx_customer_duplicate_candidates_primary_customer_id", table_name="customer_duplicate_candidates")
    alembic_op.drop_index("idx_customer_duplicate_candidates_status_detected_at", table_name="customer_duplicate_candidates")
    alembic_op.drop_table("customer_duplicate_candidates")
    alembic_op.drop_column("customer_preferences", "confirmed_at")
    alembic_op.drop_constraint("uq_customers_phone_normalized", "customers", type_="unique")
    alembic_op.drop_column("customers", "phone_normalized")