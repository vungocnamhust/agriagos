# pyright: reportAttributeAccessIssue=false
"""Add farm summary board read-model view.

Revision ID: 20260411_0010
Revises: 20260411_0009
Create Date: 2026-04-11 00:00:10
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260411_0010"
down_revision = "20260411_0009"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


FARM_SUMMARY_BOARD_SQL = """
    CREATE OR REPLACE VIEW farm_summary_board AS
    SELECT
        p.plot_id,
        p.plot_code,
        p.name AS plot_name,
        p.location_text,
        p.area_value,
        p.area_unit,
        p.status AS plot_status,
        c.crop_cycle_id,
        c.crop_name,
        c.growth_stage,
        c.status AS crop_cycle_status,
        c.expected_harvest_from,
        c.expected_harvest_to,
        c.estimated_yield_qty
    FROM plots p
    LEFT JOIN crop_cycles c
        ON c.plot_id = p.plot_id
       AND c.status NOT IN ('closed', 'cancelled')
"""


def upgrade() -> None:
    alembic_op.execute(FARM_SUMMARY_BOARD_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS farm_summary_board")