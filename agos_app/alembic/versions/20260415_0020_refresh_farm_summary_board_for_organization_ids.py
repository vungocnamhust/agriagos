"""Refresh farm summary board view for organization ids.

Revision ID: 20260415_0020
Revises: 20260415_0019
Create Date: 2026-04-15 13:00:00
"""
from __future__ import annotations

import importlib
from typing import Any


revision = "20260415_0020"
down_revision = "20260415_0019"
branch_labels = None
depends_on = None


alembic_op: Any = importlib.import_module("alembic.op")


UPDATED_FARM_SUMMARY_BOARD_SQL = """
    CREATE OR REPLACE VIEW farm_summary_board AS
    SELECT
        p.plot_id,
        p.plot_code,
        p.organization_id AS plot_organization_id,
        p.name AS plot_name,
        p.location_text,
        p.area_value,
        p.area_unit,
        p.status AS plot_status,
        c.crop_cycle_id,
        c.organization_id AS crop_cycle_organization_id,
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


PREVIOUS_FARM_SUMMARY_BOARD_SQL = """
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
    alembic_op.execute("DROP VIEW IF EXISTS farm_summary_board")
    alembic_op.execute(UPDATED_FARM_SUMMARY_BOARD_SQL)


def downgrade() -> None:
    alembic_op.execute("DROP VIEW IF EXISTS farm_summary_board")
    alembic_op.execute(PREVIOUS_FARM_SUMMARY_BOARD_SQL)