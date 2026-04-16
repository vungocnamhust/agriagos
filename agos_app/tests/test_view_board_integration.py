# pyright: reportMissingImports=false, reportMissingModuleSource=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.store import _db
from app.store import farm as farm_store
from app.store import views as view_store
from app.services import views as views_service


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


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
                phone_normalized,
                status,
                tags
            ) VALUES (
                CAST(:customer_id AS uuid),
                :customer_code,
                :full_name,
                :phone,
                :phone_normalized,
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
            "phone_normalized": f"0900{customer_id.replace('-', '')[:6]}",
        },
    )


def _insert_organization(session: Session, organization_id: str, organization_code: str, name: str) -> None:
    session.execute(
        text(
            """
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                'family_business',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": organization_code,
            "name": name,
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
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                'family_business',
                'active'
            )
            ON CONFLICT (organization_id) DO NOTHING
            """
        ),
        {
            "organization_id": str(uuid.uuid4()),
            "organization_code": f"ORG-LOT-{code_suffix}",
            "name": "Lot View Org",
        },
    )
    organization_id = postgres_db_session.execute(
        text(
            """
            SELECT organization_id
            FROM organizations
            WHERE organization_code = :organization_code
            """
        ),
        {"organization_code": f"ORG-LOT-{code_suffix}"},
    ).scalar_one()

    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                lot_code,
                organization_id,
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
                CAST(:organization_id AS uuid),
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
                NULL,
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
                NULL,
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
                NULL,
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
            "organization_id": str(organization_id),
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
    assert scoped_filtered_rows[0]["organizationId"] == str(organization_id)
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
    organization_id = str(uuid.uuid4())
    _insert_customer(postgres_db_session, customer_1, f"KH-PEND-{code_suffix}-1", "Alice Pending")
    _insert_customer(postgres_db_session, customer_2, f"KH-PEND-{code_suffix}-2", "Bao Pending")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                'family_business',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": f"ORG-PEND-{code_suffix}",
            "name": "Pending Org",
        },
    )

    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                order_code,
                organization_id,
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
                CAST(:organization_id AS uuid),
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
                NULL,
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
                NULL,
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
                NULL,
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
            "organization_id": organization_id,
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
    assert [row["organizationId"] for row in scoped_rows] == [organization_id, None, None]


@pytest.mark.postgres_integration
def test_fetch_farm_store_and_summary_board_return_expected_postgres_rows(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    _enable_farm_store(monkeypatch, postgres_db_session)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    plot_1 = str(uuid.uuid4())
    plot_2 = str(uuid.uuid4())
    cycle_active = str(uuid.uuid4())
    cycle_closed = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, f"ORG-FARM-{code_suffix}", "Farm Org")

    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (
                plot_id,
                plot_code,
                organization_id,
                name,
                location_text,
                area_value,
                area_unit,
                status
            ) VALUES
            (
                CAST(:plot_1 AS uuid),
                :plot_code_1,
                CAST(:organization_id AS uuid),
                'Garden A',
                'Da Lat',
                2.5,
                'ha',
                'active'
            ),
            (
                CAST(:plot_2 AS uuid),
                :plot_code_2,
                NULL,
                'Garden B',
                'Bao Loc',
                1.0,
                'ha',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
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
                organization_id,
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
                CAST(:organization_id AS uuid),
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
                NULL,
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
            "organization_id": organization_id,
            "plot_1": plot_1,
        },
    )

    plots = farm_store.fetch_plots()
    active_cycles = farm_store.fetch_crop_cycles(plot_1, "active")
    summary_rows = view_store.fetch_farm_summary_board()
    scoped_plots = [plot for plot in plots if plot["plotCode"].startswith(f"PLOT-IT-{code_suffix}-")]
    scoped_summary_rows = [row for row in summary_rows if row["plotCode"].startswith(f"PLOT-IT-{code_suffix}-")]

    assert [plot["plotCode"] for plot in scoped_plots] == [f"PLOT-IT-{code_suffix}-1", f"PLOT-IT-{code_suffix}-2"]
    assert scoped_plots[0]["organizationId"] == organization_id
    assert scoped_plots[1]["organizationId"] is None
    assert active_cycles == [
        {
            "cropCycleId": cycle_active,
            "plotId": plot_1,
            "organizationId": organization_id,
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
    assert scoped_summary_rows[1]["estimatedYieldQty"] is None


@pytest.mark.postgres_integration
def test_customer_360_endpoint_reads_real_postgres_projection(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    customer_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())
    preorder_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    order_line_id = str(uuid.uuid4())
    _insert_customer(postgres_db_session, customer_id, f"KH-EP-{code_suffix}", "Endpoint Customer")
    _insert_product_sku(postgres_db_session, sku_id, f"SKU-EP-{code_suffix}", "Endpoint Rice")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO customer_preferences (
                preference_id,
                customer_id,
                preference_type,
                preference_value,
                source,
                confidence_level
            ) VALUES (
                gen_random_uuid(),
                CAST(:customer_id AS uuid),
                'pack_size',
                '5kg',
                'human',
                0.95
            )
            """
        ),
        {"customer_id": customer_id},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO preorders (
                preorder_id,
                preorder_code,
                customer_id,
                product_sku_id,
                committed_qty,
                allocated_qty,
                delivered_qty,
                cancelled_qty,
                remaining_qty,
                status
            ) VALUES (
                CAST(:preorder_id AS uuid),
                :preorder_code,
                CAST(:customer_id AS uuid),
                CAST(:product_sku_id AS uuid),
                12,
                2,
                1,
                0,
                9,
                'active'
            )
            """
        ),
        {
            "preorder_id": preorder_id,
            "preorder_code": f"DT-EP-{code_suffix}",
            "customer_id": customer_id,
            "product_sku_id": sku_id,
        },
    )
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
                payment_status,
                source_preorder_flag
            ) VALUES (
                CAST(:order_id AS uuid),
                :order_code,
                CAST(:customer_id AS uuid),
                'zalo',
                CAST('2026-04-18T00:00:00+00:00' AS timestamptz),
                'Da Lat',
                'confirmed',
                'unpaid',
                true
            )
            """
        ),
        {
            "order_id": order_id,
            "order_code": f"ORD-EP-{code_suffix}",
            "customer_id": customer_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_order_lines (
                order_line_id,
                order_id,
                product_sku_id,
                ordered_qty,
                allocated_qty,
                packed_qty,
                delivered_qty,
                unit,
                source_preorder_id,
                status
            ) VALUES (
                CAST(:order_line_id AS uuid),
                CAST(:order_id AS uuid),
                CAST(:product_sku_id AS uuid),
                4,
                1,
                0,
                0,
                'kg',
                CAST(:source_preorder_id AS uuid),
                'allocated'
            )
            """
        ),
        {
            "order_line_id": order_line_id,
            "order_id": order_id,
            "product_sku_id": sku_id,
            "source_preorder_id": preorder_id,
        },
    )

    response = client.get(
        f"/api/v1/views/customer-360/{customer_id}",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["customer"]["customerId"] == customer_id
    assert payload["customer"]["fullName"] == "Endpoint Customer"
    assert [item["preorderCode"] for item in payload["activePreorders"]] == [f"DT-EP-{code_suffix}"]
    assert payload["activePreorders"][0]["remainingQty"] == 9
    assert [item["orderCode"] for item in payload["recentOrders"]] == [f"ORD-EP-{code_suffix}"]
    assert payload["recentOrders"][0]["lines"][0]["orderLineId"] == order_line_id
    assert payload["preferences"] == [
        {
            "preferenceType": "pack_size",
            "preferenceValue": "5kg",
            "confidenceLevel": 0.95,
        }
    ]


@pytest.mark.postgres_integration
def test_available_lots_endpoint_reads_real_postgres_projection(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    sku_id = str(uuid.uuid4())
    _insert_product_sku(postgres_db_session, sku_id, f"SKU-AL-{code_suffix}", "Available Rice")
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
                CAST(:product_sku_id AS uuid),
                'crop_cycle',
                'cycle-a',
                CAST('2026-04-20T00:00:00+00:00' AS timestamptz),
                10,
                6,
                0,
                6,
                'released'
            ),
            (
                CAST(:lot_id_2 AS uuid),
                :lot_code_2,
                CAST(:product_sku_id AS uuid),
                'crop_cycle',
                'cycle-b',
                CAST('2026-04-19T00:00:00+00:00' AS timestamptz),
                10,
                0,
                0,
                6,
                'released'
            )
            """
        ),
        {
            "lot_id_1": str(uuid.uuid4()),
            "lot_code_1": f"LOT-AL-{code_suffix}-1",
            "lot_id_2": str(uuid.uuid4()),
            "lot_code_2": f"LOT-AL-{code_suffix}-2",
            "product_sku_id": sku_id,
        },
    )

    response = client.get("/api/v1/views/available-lots", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))
    scoped_rows = [row for row in response.json()["items"] if row["lotCode"].startswith(f"LOT-AL-{code_suffix}-")]

    assert response.status_code == 200
    assert [row["lotCode"] for row in scoped_rows] == [f"LOT-AL-{code_suffix}-1"]
    assert scoped_rows[0]["status"] == "released"


@pytest.mark.postgres_integration
def test_pending_fulfillment_endpoint_reads_real_postgres_projection(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    customer_id = str(uuid.uuid4())
    organization_id = str(uuid.uuid4())
    _insert_customer(postgres_db_session, customer_id, f"KH-PF-{code_suffix}", "Pending Endpoint")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                'family_business',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": f"ORG-PF-{code_suffix}",
            "name": "Pending Endpoint Org",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                order_code,
                organization_id,
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
                CAST(:organization_id AS uuid),
                CAST(:customer_id AS uuid),
                'phone',
                CAST('2026-04-16T00:00:00+00:00' AS timestamptz),
                'Da Lat',
                'confirmed',
                'unpaid'
            ),
            (
                CAST(:order_id_2 AS uuid),
                :order_code_2,
                NULL,
                CAST(:customer_id AS uuid),
                'phone',
                NULL,
                'Da Lat',
                'packed',
                'unpaid'
            )
            """
        ),
        {
            "order_id_1": str(uuid.uuid4()),
            "order_code_1": f"ORD-PF-{code_suffix}-1",
            "order_id_2": str(uuid.uuid4()),
            "order_code_2": f"ORD-PF-{code_suffix}-2",
            "customer_id": customer_id,
            "organization_id": organization_id,
        },
    )

    response = client.get("/api/v1/views/pending-fulfillment", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))
    scoped_rows = [row for row in response.json()["items"] if row["orderCode"].startswith(f"ORD-PF-{code_suffix}-")]

    assert response.status_code == 200
    assert [row["orderCode"] for row in scoped_rows] == [f"ORD-PF-{code_suffix}-1", f"ORD-PF-{code_suffix}-2"]
    assert [row["organizationId"] for row in scoped_rows] == [organization_id, None]
    assert [row["status"] for row in scoped_rows] == ["confirmed", "packed"]


@pytest.mark.postgres_integration
def test_farm_summary_board_endpoint_reads_real_postgres_projection(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    plot_id = str(uuid.uuid4())
    crop_cycle_id = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, f"ORG-EP-{code_suffix}", "Endpoint Org")

    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (
                plot_id,
                plot_code,
                organization_id,
                name,
                location_text,
                area_value,
                area_unit,
                status
            ) VALUES (
                CAST(:plot_id AS uuid),
                :plot_code,
                CAST(:organization_id AS uuid),
                'Endpoint Plot',
                'Da Lat',
                3.0,
                'ha',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "plot_id": plot_id,
            "plot_code": f"PLOT-EP-{code_suffix}",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO crop_cycles (
                crop_cycle_id,
                plot_id,
                organization_id,
                crop_name,
                start_date,
                growth_stage,
                status,
                expected_harvest_from,
                expected_harvest_to,
                estimated_yield_qty
            ) VALUES (
                CAST(:crop_cycle_id AS uuid),
                CAST(:plot_id AS uuid),
                CAST(:organization_id AS uuid),
                'Coffee',
                CAST('2026-03-15' AS date),
                'flowering_or_maturing',
                'near_harvest',
                CAST('2026-06-01T00:00:00+00:00' AS timestamptz),
                CAST('2026-06-15T00:00:00+00:00' AS timestamptz),
                88
            )
            """
        ),
        {
            "crop_cycle_id": crop_cycle_id,
            "organization_id": organization_id,
            "plot_id": plot_id,
        },
    )

    response = client.get("/api/v1/views/farm-summary-board", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))
    payload = response.json()["items"]
    scoped_rows = [row for row in payload if row["plotCode"] == f"PLOT-EP-{code_suffix}"]

    assert response.status_code == 200
    assert len(scoped_rows) == 1
    assert scoped_rows[0]["cropCycleId"] == crop_cycle_id
    assert scoped_rows[0]["plotOrganizationId"] == organization_id
    assert scoped_rows[0]["cropCycleOrganizationId"] == organization_id
    assert scoped_rows[0]["growthStage"] == "maturing"
    assert scoped_rows[0]["cropCycleStatus"] == "near_harvest"
    assert scoped_rows[0]["estimatedYieldQty"] == 88.0


@pytest.mark.postgres_integration
def test_project_contribution_summary_endpoint_reads_real_postgres_aggregation(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    project_scope_code = f"PRJ-SUM-{code_suffix}"

    _insert_organization(postgres_db_session, organization_id, f"ORG-SUM-{code_suffix}", "Summary Org")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                metadata_json
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                'Summary Scope',
                'value_stream',
                'active',
                '2026',
                'founder-1',
                '{}'::jsonb
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": project_scope_code,
        },
    )

    assignment_ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
    target_ids = [str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())]
    for assignment_id, target_id in zip(assignment_ids, target_ids, strict=True):
        postgres_db_session.execute(
            text(
                """
                INSERT INTO project_assignments (
                    project_assignment_id,
                    project_scope_id,
                    target_type,
                    target_id,
                    is_primary,
                    attribution_weight,
                    metadata_json
                ) VALUES (
                    CAST(:project_assignment_id AS uuid),
                    CAST(:project_scope_id AS uuid),
                    'lot',
                    CAST(:target_id AS uuid),
                    true,
                    1,
                    '{}'::jsonb
                )
                """
            ),
            {
                "project_assignment_id": assignment_id,
                "project_scope_id": project_scope_id,
                "target_id": target_id,
            },
        )

    contribution_rows = [
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_ids[0],
            "actor_id": str(uuid.uuid4()),
            "target_id": target_ids[0],
            "status": "confirmed",
            "quantity": 3,
            "estimated_value": 900000,
            "created_at": "2026-04-16T09:00:00+00:00",
        },
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_ids[1],
            "actor_id": str(uuid.uuid4()),
            "target_id": target_ids[1],
            "status": "confirmed",
            "quantity": 2,
            "estimated_value": 600000,
            "created_at": "2026-04-16T10:00:00+00:00",
        },
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_ids[2],
            "actor_id": str(uuid.uuid4()),
            "target_id": target_ids[2],
            "status": "rejected",
            "quantity": 1,
            "estimated_value": 200000,
            "created_at": "2026-04-16T11:00:00+00:00",
        },
    ]
    for row in contribution_rows:
        postgres_db_session.execute(
            text(
                """
                INSERT INTO project_contribution_events (
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    source,
                    created_at,
                    updated_at
                ) VALUES (
                    CAST(:project_contribution_event_id AS uuid),
                    CAST(:project_scope_id AS uuid),
                    CAST(:project_assignment_id AS uuid),
                    CAST(:organization_id AS uuid),
                    CAST(:actor_id AS uuid),
                    'lot',
                    CAST(:subject_id AS uuid),
                    'labor_day',
                    'producer',
                    :quantity,
                    'day',
                    :estimated_value,
                    'VND',
                    :status,
                    'manual',
                    CAST(:created_at AS timestamptz),
                    CAST(:created_at AS timestamptz)
                )
                """
            ),
            {
                "project_contribution_event_id": row["event_id"],
                "project_scope_id": project_scope_id,
                "project_assignment_id": row["assignment_id"],
                "organization_id": organization_id,
                "actor_id": row["actor_id"],
                "subject_id": row["target_id"],
                "quantity": row["quantity"],
                "estimated_value": row["estimated_value"],
                "status": row["status"],
                "created_at": row["created_at"],
            },
        )

    response = client.get(
        f"/api/v1/views/project-contribution-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    scoped_rows = [row for row in payload if row["projectScopeId"] == project_scope_id]
    assert len(scoped_rows) == 1
    assert scoped_rows[0]["projectScopeCode"] == project_scope_code
    assert scoped_rows[0]["projectScopeName"] == "Summary Scope"
    assert scoped_rows[0]["proposedCount"] == 0
    assert scoped_rows[0]["confirmedCount"] == 2
    assert scoped_rows[0]["rejectedCount"] == 1
    assert scoped_rows[0]["confirmedQuantity"] == 5.0
    assert scoped_rows[0]["confirmedEstimatedValue"] == 1500000.0
    assert scoped_rows[0]["currency"] == "VND"


@pytest.mark.postgres_integration
def test_project_contribution_summary_endpoint_nulls_estimated_value_when_confirmed_rows_have_no_values(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    assignment_id = str(uuid.uuid4())
    subject_id = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, f"ORG-SUM-NULL-{code_suffix}", "Summary Null Org")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                metadata_json
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                'Summary Null Scope',
                'value_stream',
                'active',
                '2026',
                'founder-1',
                '{}'::jsonb
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": f"PRJ-SUM-NULL-{code_suffix}",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_assignments (
                project_assignment_id,
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                metadata_json
            ) VALUES (
                CAST(:project_assignment_id AS uuid),
                CAST(:project_scope_id AS uuid),
                'lot',
                CAST(:target_id AS uuid),
                true,
                1,
                '{}'::jsonb
            )
            """
        ),
        {
            "project_assignment_id": assignment_id,
            "project_scope_id": project_scope_id,
            "target_id": subject_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_contribution_events (
                project_contribution_event_id,
                project_scope_id,
                project_assignment_id,
                organization_id,
                actor_id,
                subject_type,
                subject_id,
                contribution_type,
                role,
                quantity,
                unit,
                estimated_value,
                currency,
                status,
                source,
                created_at,
                updated_at
            ) VALUES (
                CAST(:project_contribution_event_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:project_assignment_id AS uuid),
                CAST(:organization_id AS uuid),
                CAST(:actor_id AS uuid),
                'lot',
                CAST(:subject_id AS uuid),
                'labor_day',
                'producer',
                2,
                'day',
                NULL,
                NULL,
                'confirmed',
                'manual',
                CAST('2026-04-16T09:00:00+00:00' AS timestamptz),
                CAST('2026-04-16T09:00:00+00:00' AS timestamptz)
            )
            """
        ),
        {
            "project_contribution_event_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "project_assignment_id": assignment_id,
            "organization_id": organization_id,
            "actor_id": str(uuid.uuid4()),
            "subject_id": subject_id,
        },
    )

    response = client.get(
        f"/api/v1/views/project-contribution-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["confirmedCount"] == 1
    assert payload[0]["confirmedQuantity"] == 2.0
    assert payload[0]["confirmedEstimatedValue"] is None
    assert payload[0]["currency"] is None


@pytest.mark.postgres_integration
def test_project_contribution_ledger_endpoint_reads_real_postgres_rows(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    project_scope_code = f"PRJ-LEDGER-{code_suffix}"
    assignment_id_1 = str(uuid.uuid4())
    assignment_id_2 = str(uuid.uuid4())
    target_id_1 = str(uuid.uuid4())
    target_id_2 = str(uuid.uuid4())
    event_id_1 = str(uuid.uuid4())
    event_id_2 = str(uuid.uuid4())
    actor_id_1 = str(uuid.uuid4())
    actor_id_2 = str(uuid.uuid4())
    confirmer_id = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, f"ORG-LEDGER-{code_suffix}", "Ledger Org")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                metadata_json
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                'Ledger Scope',
                'value_stream',
                'active',
                '2026',
                'founder-1',
                '{}'::jsonb
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": project_scope_code,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_assignments (
                project_assignment_id,
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                metadata_json
            ) VALUES
            (
                CAST(:assignment_id_1 AS uuid),
                CAST(:project_scope_id AS uuid),
                'order',
                CAST(:target_id_1 AS uuid),
                true,
                1,
                '{}'::jsonb
            ),
            (
                CAST(:assignment_id_2 AS uuid),
                CAST(:project_scope_id AS uuid),
                'lot',
                CAST(:target_id_2 AS uuid),
                true,
                0.5,
                '{}'::jsonb
            )
            """
        ),
        {
            "assignment_id_1": assignment_id_1,
            "assignment_id_2": assignment_id_2,
            "project_scope_id": project_scope_id,
            "target_id_1": target_id_1,
            "target_id_2": target_id_2,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_contribution_events (
                project_contribution_event_id,
                project_scope_id,
                project_assignment_id,
                organization_id,
                actor_id,
                subject_type,
                subject_id,
                contribution_type,
                role,
                quantity,
                unit,
                estimated_value,
                currency,
                status,
                confirmed_by,
                confirmed_at,
                source,
                metadata_json,
                created_at,
                updated_at
            ) VALUES
            (
                CAST(:event_id_1 AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:assignment_id_1 AS uuid),
                CAST(:organization_id AS uuid),
                CAST(:actor_id_1 AS uuid),
                'order',
                CAST(:target_id_1 AS uuid),
                'cash_support',
                'supporter',
                2,
                'entry',
                350000,
                'VND',
                'proposed',
                NULL,
                NULL,
                'manual',
                '{"actorType":"partner","verificationStatus":"system_detected","verificationSource":"field_log"}'::jsonb,
                CAST('2026-04-16T11:00:00+00:00' AS timestamptz),
                CAST('2026-04-16T11:00:00+00:00' AS timestamptz)
            ),
            (
                CAST(:event_id_2 AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:assignment_id_2 AS uuid),
                CAST(:organization_id AS uuid),
                CAST(:actor_id_2 AS uuid),
                'lot',
                CAST(:target_id_2 AS uuid),
                'labor_day',
                'producer',
                1,
                'day',
                NULL,
                NULL,
                'confirmed',
                CAST(:confirmer_id AS uuid),
                CAST('2026-04-16T10:30:00+00:00' AS timestamptz),
                'manual',
                '{"actorType":"person","verificationStatus":"verified","verificationSource":"admin_confirmed"}'::jsonb,
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz),
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz)
            )
            """
        ),
        {
            "event_id_1": event_id_1,
            "event_id_2": event_id_2,
            "project_scope_id": project_scope_id,
            "assignment_id_1": assignment_id_1,
            "assignment_id_2": assignment_id_2,
            "organization_id": organization_id,
            "actor_id_1": actor_id_1,
            "actor_id_2": actor_id_2,
            "target_id_1": target_id_1,
            "target_id_2": target_id_2,
            "confirmer_id": confirmer_id,
        },
    )

    response = client.get(
        f"/api/v1/views/project-contribution-ledger?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert [row["projectContributionEventId"] for row in payload] == [event_id_2, event_id_1]
    assert payload[0]["projectScopeCode"] == project_scope_code
    assert payload[0]["assignmentTargetType"] == "lot"
    assert payload[0]["assignmentTargetId"] == target_id_2
    assert payload[0]["status"] == "confirmed"
    assert payload[0]["confirmedBy"] == confirmer_id
    assert payload[0]["verificationStatus"] == "verified"
    assert payload[1]["assignmentTargetType"] == "order"
    assert payload[1]["assignmentTargetId"] == target_id_1
    assert payload[1]["actorType"] == "partner"
    assert payload[1]["estimatedValue"] == 350000.0
    assert payload[1]["currency"] == "VND"


@pytest.mark.postgres_integration
def test_project_pnl_summary_endpoint_reads_real_postgres_aggregation(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    project_scope_code = "PRJ-PNL-001"
    customer_id = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, "ORG-PNL-001", "PnL Org")
    _insert_customer(postgres_db_session, customer_id, "KH-PNL-001", "PnL Customer")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                'PnL Scope',
                'value_stream',
                'active'
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": project_scope_code,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_cost_records (
                cost_record_id,
                project_scope_id,
                organization_id,
                cost_type,
                amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                attribution_policy,
                metadata_json,
                created_at
            ) VALUES (
                CAST(:cost_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'labor_payout',
                :amount,
                'VND',
                CAST(:recognized_at AS timestamptz),
                'project_contribution_event',
                CAST(:source_object_id AS uuid),
                'direct_source_link',
                '{}'::jsonb,
                CAST(:created_at AS timestamptz)
            )
            """
        ),
        {
            "cost_record_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "amount": 400000,
            "recognized_at": "2026-04-16T09:00:00+00:00",
            "source_object_id": str(uuid.uuid4()),
            "created_at": "2026-04-16T09:00:00+00:00",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_cost_records (
                cost_record_id,
                project_scope_id,
                organization_id,
                cost_type,
                amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                attribution_policy,
                metadata_json,
                created_at
            ) VALUES (
                CAST(:cost_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'labor_payout',
                :amount,
                'VND',
                CAST(:recognized_at AS timestamptz),
                'project_contribution_event',
                CAST(:source_object_id AS uuid),
                'direct_source_link',
                '{}'::jsonb,
                CAST(:created_at AS timestamptz)
            )
            """
        ),
        {
            "cost_record_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "amount": 150000,
            "recognized_at": "2026-04-16T10:00:00+00:00",
            "source_object_id": str(uuid.uuid4()),
            "created_at": "2026-04-16T10:00:00+00:00",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_revenue_records (
                revenue_record_id,
                project_scope_id,
                organization_id,
                customer_id,
                revenue_type,
                gross_amount,
                net_amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                metadata_json,
                created_at
            ) VALUES (
                CAST(:revenue_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                CAST(:customer_id AS uuid),
                'delivered_order_sale',
                :gross_amount,
                :net_amount,
                'VND',
                CAST(:recognized_at AS timestamptz),
                'order',
                CAST(:source_object_id AS uuid),
                '{}'::jsonb,
                CAST(:created_at AS timestamptz)
            )
            """
        ),
        {
            "revenue_record_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "customer_id": customer_id,
            "gross_amount": 900000,
            "net_amount": 850000,
            "recognized_at": "2026-04-16T11:00:00+00:00",
            "source_object_id": str(uuid.uuid4()),
            "created_at": "2026-04-16T11:00:00+00:00",
        },
    )

    response = client.get(
        f"/api/v1/views/project-pnl-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    scoped_rows = [row for row in payload if row["projectScopeId"] == project_scope_id]
    assert len(scoped_rows) == 1
    assert scoped_rows[0]["projectScopeCode"] == project_scope_code
    assert scoped_rows[0]["projectScopeName"] == "PnL Scope"
    assert scoped_rows[0]["costRecordCount"] == 2
    assert scoped_rows[0]["revenueRecordCount"] == 1
    assert scoped_rows[0]["recognizedCostAmount"] == 550000.0
    assert scoped_rows[0]["recognizedRevenueNetAmount"] == 850000.0
    assert scoped_rows[0]["marginAmount"] == 300000.0
    assert scoped_rows[0]["currency"] == "VND"


@pytest.mark.postgres_integration
def test_project_pnl_summary_endpoint_nulls_currency_for_mixed_financial_currencies(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, "ORG-PNL-MIXED", "PnL Mixed Org")
    _insert_customer(postgres_db_session, customer_id, "KH-PNL-MIXED", "Mixed Currency Customer")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'PRJ-PNL-MIXED',
                'PnL Mixed Scope',
                'value_stream',
                'active'
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_cost_records (
                cost_record_id,
                project_scope_id,
                organization_id,
                cost_type,
                amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                attribution_policy,
                metadata_json,
                created_at
            ) VALUES (
                CAST(:cost_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'labor_payout',
                100000,
                'VND',
                CAST('2026-04-16T09:00:00+00:00' AS timestamptz),
                'project_contribution_event',
                CAST(:source_object_id AS uuid),
                'direct_source_link',
                '{}'::jsonb,
                CAST('2026-04-16T09:00:00+00:00' AS timestamptz)
            )
            """
        ),
        {
            "cost_record_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "source_object_id": str(uuid.uuid4()),
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_revenue_records (
                revenue_record_id,
                project_scope_id,
                organization_id,
                customer_id,
                revenue_type,
                gross_amount,
                net_amount,
                currency,
                recognized_at,
                source_object_type,
                source_object_id,
                metadata_json,
                created_at
            ) VALUES (
                CAST(:revenue_record_id AS uuid),
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                CAST(:customer_id AS uuid),
                'delivered_order_sale',
                75,
                50,
                'USD',
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz),
                'order',
                CAST(:source_object_id AS uuid),
                '{}'::jsonb,
                CAST('2026-04-16T10:00:00+00:00' AS timestamptz)
            )
            """
        ),
        {
            "revenue_record_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "customer_id": customer_id,
            "source_object_id": str(uuid.uuid4()),
        },
    )

    response = client.get(
        f"/api/v1/views/project-pnl-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["projectScopeId"] == project_scope_id
    assert payload[0]["recognizedCostAmount"] == 100000.0
    assert payload[0]["recognizedRevenueNetAmount"] == 50.0
    assert payload[0]["marginAmount"] == -99950.0
    assert payload[0]["currency"] is None


@pytest.mark.postgres_integration
def test_project_order_allocation_summary_endpoint_reads_real_postgres_aggregation(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    customer_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    order_line_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())
    lot_id_1 = str(uuid.uuid4())
    lot_id_2 = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, "ORG-ALLOC-SUM", "Allocation Summary Org")
    _insert_customer(postgres_db_session, customer_id, "KH-ALLOC-SUM", "Allocation Customer")
    _insert_product_sku(postgres_db_session, sku_id, "SKU-ALLOC-SUM", "Allocation Summary SKU")

    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                'PRJ-ALLOC-SUM',
                'Allocation Summary Scope',
                'value_stream',
                'active'
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_assignments (
                project_assignment_id,
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                metadata_json
            ) VALUES (
                CAST(:project_assignment_id AS uuid),
                CAST(:project_scope_id AS uuid),
                'order',
                CAST(:target_id AS uuid),
                true,
                1,
                '{}'::jsonb
            )
            """
        ),
        {
            "project_assignment_id": str(uuid.uuid4()),
            "project_scope_id": project_scope_id,
            "target_id": order_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_orders (
                order_id,
                order_code,
                organization_id,
                customer_id,
                channel,
                shipping_address,
                status,
                payment_status
            ) VALUES (
                CAST(:order_id AS uuid),
                'ORD-ALLOC-SUM',
                CAST(:organization_id AS uuid),
                CAST(:customer_id AS uuid),
                'phone',
                'Da Lat',
                'allocated',
                'unpaid'
            )
            """
        ),
        {
            "order_id": order_id,
            "organization_id": organization_id,
            "customer_id": customer_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO sales_order_lines (
                order_line_id,
                order_id,
                product_sku_id,
                ordered_qty,
                allocated_qty,
                packed_qty,
                delivered_qty,
                unit,
                status
            ) VALUES (
                CAST(:order_line_id AS uuid),
                CAST(:order_id AS uuid),
                CAST(:product_sku_id AS uuid),
                5,
                5,
                0,
                0,
                'kg',
                'allocated'
            )
            """
        ),
        {
            "order_line_id": order_line_id,
            "order_id": order_id,
            "product_sku_id": sku_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                lot_code,
                organization_id,
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
                'LOT-ALLOC-SUM-1',
                CAST(:organization_id AS uuid),
                CAST(:product_sku_id AS uuid),
                'crop_cycle',
                'cycle-alloc-1',
                CAST('2026-04-14T00:00:00+00:00' AS timestamptz),
                5,
                3,
                0,
                3,
                'released'
            ),
            (
                CAST(:lot_id_2 AS uuid),
                'LOT-ALLOC-SUM-2',
                CAST(:organization_id AS uuid),
                CAST(:product_sku_id AS uuid),
                'crop_cycle',
                'cycle-alloc-2',
                CAST('2026-04-15T00:00:00+00:00' AS timestamptz),
                5,
                2,
                0,
                2,
                'released'
            )
            """
        ),
        {
            "lot_id_1": lot_id_1,
            "lot_id_2": lot_id_2,
            "organization_id": organization_id,
            "product_sku_id": sku_id,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO allocations (
                allocation_id,
                order_line_id,
                lot_id,
                allocated_qty,
                status,
                allocated_at
            ) VALUES
            (
                CAST(:allocation_id_1 AS uuid),
                CAST(:order_line_id AS uuid),
                CAST(:lot_id_1 AS uuid),
                3,
                'active',
                now()
            ),
            (
                CAST(:allocation_id_2 AS uuid),
                CAST(:order_line_id AS uuid),
                CAST(:lot_id_2 AS uuid),
                2,
                'released',
                now()
            )
            """
        ),
        {
            "allocation_id_1": str(uuid.uuid4()),
            "allocation_id_2": str(uuid.uuid4()),
            "order_line_id": order_line_id,
            "lot_id_1": lot_id_1,
            "lot_id_2": lot_id_2,
        },
    )

    response = client.get(
        f"/api/v1/views/project-order-allocation-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="ops", actor_id="ops-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 1
    assert payload[0]["projectScopeId"] == project_scope_id
    assert payload[0]["projectScopeCode"] == "PRJ-ALLOC-SUM"
    assert payload[0]["projectScopeName"] == "Allocation Summary Scope"
    assert payload[0]["assignedOrderCount"] == 1
    assert payload[0]["allocatedOrderCount"] == 1
    assert payload[0]["allocationCount"] == 2
    assert payload[0]["activeAllocationCount"] == 1
    assert payload[0]["releasedAllocationCount"] == 1
    assert payload[0]["allocatedQty"] == 5.0
    assert payload[0]["activeAllocatedQty"] == 3.0
    assert payload[0]["releasedAllocatedQty"] == 2.0
    assert payload[0]["unit"] == "kg"


@pytest.mark.postgres_integration
def test_project_impacted_actors_summary_endpoint_reads_real_postgres_aggregation(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_view_store(monkeypatch, postgres_db_session)
    monkeypatch.setattr(views_service.postgres_sync, "is_enabled", lambda: True)

    code_suffix = uuid.uuid4().hex[:8]
    organization_id = str(uuid.uuid4())
    project_scope_id = str(uuid.uuid4())
    project_scope_code = f"PRJ-ACTOR-{code_suffix}"
    assignment_id_1 = str(uuid.uuid4())
    assignment_id_2 = str(uuid.uuid4())
    assignment_id_3 = str(uuid.uuid4())
    actor_id_1 = str(uuid.uuid4())
    actor_id_2 = str(uuid.uuid4())

    _insert_organization(postgres_db_session, organization_id, f"ORG-ACTOR-{code_suffix}", "Actor Summary Org")
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_scopes (
                project_scope_id,
                organization_id,
                project_scope_code,
                name,
                project_scope_type,
                status,
                season_year,
                owner_actor_id,
                metadata_json
            ) VALUES (
                CAST(:project_scope_id AS uuid),
                CAST(:organization_id AS uuid),
                :project_scope_code,
                'Actor Scope',
                'value_stream',
                'active',
                '2026',
                'founder-1',
                '{}'::jsonb
            )
            """
        ),
        {
            "project_scope_id": project_scope_id,
            "organization_id": organization_id,
            "project_scope_code": project_scope_code,
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO project_assignments (
                project_assignment_id,
                project_scope_id,
                target_type,
                target_id,
                is_primary,
                attribution_weight,
                metadata_json
            ) VALUES
            (
                CAST(:assignment_id_1 AS uuid),
                CAST(:project_scope_id AS uuid),
                'lot',
                CAST(:target_id_1 AS uuid),
                true,
                1,
                '{}'::jsonb
            ),
            (
                CAST(:assignment_id_2 AS uuid),
                CAST(:project_scope_id AS uuid),
                'order',
                CAST(:target_id_2 AS uuid),
                true,
                1,
                '{}'::jsonb
            ),
            (
                CAST(:assignment_id_3 AS uuid),
                CAST(:project_scope_id AS uuid),
                'lot',
                CAST(:target_id_3 AS uuid),
                true,
                1,
                '{}'::jsonb
            )
            """
        ),
        {
            "assignment_id_1": assignment_id_1,
            "assignment_id_2": assignment_id_2,
            "assignment_id_3": assignment_id_3,
            "project_scope_id": project_scope_id,
            "target_id_1": str(uuid.uuid4()),
            "target_id_2": str(uuid.uuid4()),
            "target_id_3": str(uuid.uuid4()),
        },
    )

    contribution_rows = [
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_id_1,
            "actor_id": actor_id_1,
            "metadata_json": '{"actorType":"person"}',
            "subject_type": "lot",
            "subject_id": str(uuid.uuid4()),
            "contribution_type": "labor_day",
            "role": "producer",
            "quantity": 2,
            "unit": "day",
            "estimated_value": 500000,
            "currency": "VND",
            "status": "confirmed",
            "created_at": "2026-04-16T09:00:00+00:00",
        },
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_id_2,
            "actor_id": actor_id_1,
            "metadata_json": '{"actorType":"person"}',
            "subject_type": "order",
            "subject_id": str(uuid.uuid4()),
            "contribution_type": "cash_support",
            "role": "producer",
            "quantity": 1,
            "unit": "entry",
            "estimated_value": None,
            "currency": None,
            "status": "proposed",
            "created_at": "2026-04-16T10:00:00+00:00",
        },
        {
            "event_id": str(uuid.uuid4()),
            "assignment_id": assignment_id_3,
            "actor_id": actor_id_2,
            "metadata_json": '{"actorType":"partner"}',
            "subject_type": "lot",
            "subject_id": str(uuid.uuid4()),
            "contribution_type": "labor_day",
            "role": "supporter",
            "quantity": 1,
            "unit": "day",
            "estimated_value": 100000,
            "currency": "USD",
            "status": "rejected",
            "created_at": "2026-04-16T11:00:00+00:00",
        },
    ]
    for row in contribution_rows:
        postgres_db_session.execute(
            text(
                """
                INSERT INTO project_contribution_events (
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    source,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    CAST(:project_contribution_event_id AS uuid),
                    CAST(:project_scope_id AS uuid),
                    CAST(:project_assignment_id AS uuid),
                    CAST(:organization_id AS uuid),
                    CAST(:actor_id AS uuid),
                    :subject_type,
                    CAST(:subject_id AS uuid),
                    :contribution_type,
                    :role,
                    :quantity,
                    :unit,
                    :estimated_value,
                    :currency,
                    :status,
                    'manual',
                    CAST(:metadata_json AS jsonb),
                    CAST(:created_at AS timestamptz),
                    CAST(:created_at AS timestamptz)
                )
                """
            ),
            {
                "project_contribution_event_id": row["event_id"],
                "project_scope_id": project_scope_id,
                "project_assignment_id": row["assignment_id"],
                "organization_id": organization_id,
                "actor_id": row["actor_id"],
                "subject_type": row["subject_type"],
                "subject_id": row["subject_id"],
                "contribution_type": row["contribution_type"],
                "role": row["role"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "estimated_value": row["estimated_value"],
                "currency": row["currency"],
                "status": row["status"],
                "metadata_json": row["metadata_json"],
                "created_at": row["created_at"],
            },
        )

    response = client.get(
        f"/api/v1/views/project-impacted-actors-summary?projectScopeId={project_scope_id}",
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 200
    payload = response.json()["items"]
    assert len(payload) == 2
    assert payload[0]["projectScopeId"] == project_scope_id
    assert payload[0]["projectScopeCode"] == project_scope_code
    assert payload[0]["actorId"] == actor_id_1
    assert payload[0]["actorType"] == "person"
    assert payload[0]["role"] == "producer"
    assert payload[0]["contributionCount"] == 2
    assert payload[0]["confirmedContributionCount"] == 1
    assert payload[0]["proposedContributionCount"] == 1
    assert payload[0]["rejectedContributionCount"] == 0
    assert payload[0]["confirmedQuantity"] == 2.0
    assert payload[0]["confirmedEstimatedValue"] == 500000.0
    assert payload[0]["currency"] == "VND"
    assert payload[1]["actorId"] == actor_id_2
    assert payload[1]["actorType"] == "partner"
    assert payload[1]["role"] == "supporter"
    assert payload[1]["contributionCount"] == 1
    assert payload[1]["confirmedContributionCount"] == 0
    assert payload[1]["proposedContributionCount"] == 0
    assert payload[1]["rejectedContributionCount"] == 1
    assert payload[1]["confirmedQuantity"] == 0.0
    assert payload[1]["confirmedEstimatedValue"] is None
    assert payload[1]["currency"] is None