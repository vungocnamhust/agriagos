# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.store import _db
from app.store import farm as farm_store
from app.store import views as view_store


@contextmanager
def _bound_session_scope(session: Session) -> Iterator[Session]:
    yield session


def _enable_view_store(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(view_store, "is_enabled", lambda: True)
    monkeypatch.setattr(view_store, "SessionLocal", lambda: _bound_session_scope(session))


def _enable_farm_store(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    monkeypatch.setattr(farm_store, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda _session=None: _bound_session_scope(session))


def _insert_product_sku(session: Session, sku_id: str, sku_code: str, sku_name: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO product_skus (
                product_sku_id,
                sku_code,
                sku_name,
                unit,
                status
            ) VALUES (
                CAST(:product_sku_id AS uuid),
                :sku_code,
                :sku_name,
                'kg',
                'active'
            )
            """
        ),
        {
            "product_sku_id": sku_id,
            "sku_code": sku_code,
            "sku_name": sku_name,
        },
    )


def _insert_customer(session: Session, customer_id: str, customer_code: str, full_name: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO customers (
                customer_id,
                customer_code,
                full_name,
                phone,
                status,
                tags
            ) VALUES (
                CAST(:customer_id AS uuid),
                :customer_code,
                :full_name,
                :phone,
                'active',
                '[]'::jsonb
            )
            """
        ),
        {
            "customer_id": customer_id,
            "customer_code": customer_code,
            "full_name": full_name,
            "phone": f"0900{customer_id.replace('-', '')[:6]}",
        },
    )


@pytest.mark.postgres_integration
def test_fetch_available_lots_board_filters_to_released_positive_qty_and_honors_sku_filter(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)

    code_suffix = uuid.uuid4().hex[:8]
    sku_1 = str(uuid.uuid4())
    sku_2 = str(uuid.uuid4())
    _insert_product_sku(postgres_db_session, sku_1, f"SKU-LOT-{code_suffix}-1", "Jasmine Rice")
    _insert_product_sku(postgres_db_session, sku_2, f"SKU-LOT-{code_suffix}-2", "Black Rice")

    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                lot_code,
                product_sku_id,
                source_type,
                source_ref_id,
                harvest_or_production_date,
                actual_qty,
                available_qty,
                reserved_qty,
                released_qty,
                status
            ) VALUES
            (
                CAST(:lot_id_1 AS uuid),
                :lot_code_1,
                CAST(:sku_1 AS uuid),
                'crop_cycle',
                'cycle-a',
                CAST('2026-04-10T00:00:00+00:00' AS timestamptz),
                10,
                4,
                0,
                4,
                'released'
            ),
            (
                CAST(:lot_id_2 AS uuid),
                :lot_code_2,
                CAST(:sku_1 AS uuid),
                'crop_cycle',
                'cycle-b',
                CAST('2026-04-11T00:00:00+00:00' AS timestamptz),
                8,
                0,
                0,
                5,
                'released'
            ),
            (
                CAST(:lot_id_3 AS uuid),
                :lot_code_3,
                CAST(:sku_2 AS uuid),
                'crop_cycle',
                'cycle-c',
                CAST('2026-04-12T00:00:00+00:00' AS timestamptz),
                6,
                3,
                0,
                3,
                'released'
            ),
            (
                CAST(:lot_id_4 AS uuid),
                :lot_code_4,
                CAST(:sku_2 AS uuid),
                'crop_cycle',
                'cycle-d',
                CAST('2026-04-13T00:00:00+00:00' AS timestamptz),
                5,
                5,
                0,
                0,
                'blocked'
            )
            """
        ),
        {
            "lot_id_1": str(uuid.uuid4()),
            "lot_code_1": f"LOT-IT-{code_suffix}-1",
            "lot_id_2": str(uuid.uuid4()),
            "lot_code_2": f"LOT-IT-{code_suffix}-2",
            "lot_id_3": str(uuid.uuid4()),
            "lot_code_3": f"LOT-IT-{code_suffix}-3",
            "lot_id_4": str(uuid.uuid4()),
            "lot_code_4": f"LOT-IT-{code_suffix}-4",
            "sku_1": sku_1,
            "sku_2": sku_2,
        },
    )

    all_rows = view_store.fetch_available_lots_board(None)
    filtered_rows = view_store.fetch_available_lots_board(sku_1)
    scoped_all_rows = [row for row in all_rows if row["lotCode"].startswith(f"LOT-IT-{code_suffix}-")]
    scoped_filtered_rows = [row for row in filtered_rows if row["lotCode"].startswith(f"LOT-IT-{code_suffix}-")]

    assert [row["lotCode"] for row in scoped_all_rows] == [f"LOT-IT-{code_suffix}-3", f"LOT-IT-{code_suffix}-1"]
    assert [row["lotCode"] for row in scoped_filtered_rows] == [f"LOT-IT-{code_suffix}-1"]
    assert all(row["status"] == "released" for row in scoped_all_rows)
    assert all(row["availableQty"] > 0 for row in scoped_all_rows)


@pytest.mark.postgres_integration
def test_fetch_pending_fulfillment_board_keeps_phase1_statuses_and_sorts_by_deadline(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)

    code_suffix = uuid.uuid4().hex[:8]
    customer_1 = str(uuid.uuid4())
    customer_2 = str(uuid.uuid4())
    _insert_customer(postgres_db_session, customer_1, f"KH-PEND-{code_suffix}-1", "Alice Pending")
    _insert_customer(postgres_db_session, customer_2, f"KH-PEND-{code_suffix}-2", "Bao Pending")

    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                order_code,
                customer_id,
                channel,
                delivery_date_expected,
                shipping_address,
                status,
                payment_status
            ) VALUES
            (
                CAST(:order_id_1 AS uuid),
                :order_code_1,
                CAST(:customer_1 AS uuid),
                'zalo',
                CAST('2026-04-13T00:00:00+00:00' AS timestamptz),
                'Da Lat',
                'confirmed',
                'unpaid'
            ),
            (
                CAST(:order_id_2 AS uuid),
                :order_code_2,
                CAST(:customer_2 AS uuid),
                'phone',
                NULL,
                'Bao Loc',
                'packed',
                'unpaid'
            ),
            (
                CAST(:order_id_3 AS uuid),
                :order_code_3,
                CAST(:customer_1 AS uuid),
                'admin',
                CAST('2026-04-14T00:00:00+00:00' AS timestamptz),
                'Da Lat',
                'shipped',
                'unpaid'
            ),
            (
                CAST(:order_id_4 AS uuid),
                :order_code_4,
                CAST(:customer_2 AS uuid),
                'web',
                CAST('2026-04-12T00:00:00+00:00' AS timestamptz),
                'Bao Loc',
                'partially_packed',
                'unpaid'
            )
            """
        ),
        {
            "order_id_1": str(uuid.uuid4()),
            "order_code_1": f"ORD-PEND-{code_suffix}-1",
            "order_id_2": str(uuid.uuid4()),
            "order_code_2": f"ORD-PEND-{code_suffix}-2",
            "order_id_3": str(uuid.uuid4()),
            "order_code_3": f"ORD-PEND-{code_suffix}-3",
            "order_id_4": str(uuid.uuid4()),
            "order_code_4": f"ORD-PEND-{code_suffix}-4",
            "customer_1": customer_1,
            "customer_2": customer_2,
        },
    )

    rows = view_store.fetch_pending_fulfillment_board()
    scoped_rows = [row for row in rows if row["orderCode"].startswith(f"ORD-PEND-{code_suffix}-")]

    assert [row["orderCode"] for row in scoped_rows] == [
        f"ORD-PEND-{code_suffix}-1",
        f"ORD-PEND-{code_suffix}-3",
        f"ORD-PEND-{code_suffix}-2",
    ]
    assert [row["status"] for row in scoped_rows] == ["confirmed", "shipped", "packed"]
    assert [row["customerName"] for row in scoped_rows] == ["Alice Pending", "Alice Pending", "Bao Pending"]


@pytest.mark.postgres_integration
def test_fetch_farm_store_and_summary_board_return_expected_postgres_rows(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    _enable_farm_store(monkeypatch, postgres_db_session)

    code_suffix = uuid.uuid4().hex[:8]
    plot_1 = str(uuid.uuid4())
    plot_2 = str(uuid.uuid4())
    cycle_active = str(uuid.uuid4())
    cycle_closed = str(uuid.uuid4())

    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (
                plot_id,
                plot_code,
                name,
                location_text,
                area_value,
                area_unit,
                status
            ) VALUES
            (
                CAST(:plot_1 AS uuid),
                :plot_code_1,
                'Garden A',
                'Da Lat',
                2.5,
                'ha',
                'active'
            ),
            (
                CAST(:plot_2 AS uuid),
                :plot_code_2,
                'Garden B',
                'Bao Loc',
                1.0,
                'ha',
                'active'
            )
            """
        ),
        {
            "plot_1": plot_1,
            "plot_code_1": f"PLOT-IT-{code_suffix}-1",
            "plot_2": plot_2,
            "plot_code_2": f"PLOT-IT-{code_suffix}-2",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO crop_cycles (
                crop_cycle_id,
                plot_id,
                crop_name,
                start_date,
                growth_stage,
                status,
                expected_harvest_from,
                expected_harvest_to,
                estimated_yield_qty
            ) VALUES
            (
                CAST(:cycle_active AS uuid),
                CAST(:plot_1 AS uuid),
                'Strawberry',
                CAST('2026-03-01' AS date),
                'flowering_or_maturing',
                'active',
                CAST('2026-05-01T00:00:00+00:00' AS timestamptz),
                CAST('2026-05-10T00:00:00+00:00' AS timestamptz),
                120
            ),
            (
                CAST(:cycle_closed AS uuid),
                CAST(:plot_1 AS uuid),
                'Spinach',
                CAST('2026-02-01' AS date),
                'growing',
                'closed',
                CAST('2026-04-01T00:00:00+00:00' AS timestamptz),
                CAST('2026-04-05T00:00:00+00:00' AS timestamptz),
                50
            )
            """
        ),
        {
            "cycle_active": cycle_active,
            "cycle_closed": cycle_closed,
            "plot_1": plot_1,
        },
    )

    plots = farm_store.fetch_plots()
    active_cycles = farm_store.fetch_crop_cycles(plot_1, "active")
    summary_rows = view_store.fetch_farm_summary_board()
    scoped_plots = [plot for plot in plots if plot["plotCode"].startswith(f"PLOT-IT-{code_suffix}-")]
    scoped_summary_rows = [row for row in summary_rows if row["plotCode"].startswith(f"PLOT-IT-{code_suffix}-")]

    assert [plot["plotCode"] for plot in scoped_plots] == [f"PLOT-IT-{code_suffix}-1", f"PLOT-IT-{code_suffix}-2"]
    assert active_cycles == [
        {
            "cropCycleId": cycle_active,
            "plotId": plot_1,
            "cropName": "Strawberry",
            "growthStage": "maturing",
            "status": "active",
            "expectedHarvestFrom": "2026-05-01T00:00:00+00:00",
            "expectedHarvestTo": "2026-05-10T00:00:00+00:00",
        }
    ]
    assert [row["plotCode"] for row in scoped_summary_rows] == [f"PLOT-IT-{code_suffix}-1", f"PLOT-IT-{code_suffix}-2"]
    assert scoped_summary_rows[0]["cropCycleId"] == cycle_active
    assert scoped_summary_rows[0]["growthStage"] == "maturing"
    assert scoped_summary_rows[0]["estimatedYieldQty"] == 120.0
    assert scoped_summary_rows[1]["cropCycleId"] is None