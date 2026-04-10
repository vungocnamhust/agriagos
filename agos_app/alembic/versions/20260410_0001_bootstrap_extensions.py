# pyright: reportAttributeAccessIssue=false
"""Bootstrap PostgreSQL extensions.

Revision ID: 20260410_0001
Revises:
Create Date: 2026-04-10 00:00:01
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260410_0001"
down_revision = None
branch_labels = None
depends_on = None

alembic_op: Any = importlib.import_module("alembic.op")


def upgrade() -> None:
    alembic_op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")


def downgrade() -> None:
    alembic_op.execute("DROP EXTENSION IF EXISTS pgcrypto")