from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.orders import (
    AdjustAllocationRequest,
    AllocateItem,
    AllocateOrderRequest,
    CancelOrderRequest,
    ConfirmOrderRequest,
    CreateOrderLineRequest,
    CreateOrderRequest,
    ReleaseAllocationRequest,
    RequestCancelOrderRequest,
)
from app.services import orders as order_service
from app.store import _db


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


@pytest.mark.postgres_integration
def test_allocation_core_adjust_and_release_persist_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(order_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(order_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))

    postgres_db_session.execute(
        text(
            """
            INSERT INTO customers (
                customer_id,
                tenant_id,
                customer_code,
                full_name,
                phone,
                phone_normalized,
                channel_source,
                status,
                tags,
                notes
            ) VALUES (
                :customer_id,
                'default',
                'KH-ALLOC-001',
                'Allocation PG User',
                '+84900000001',
                '84900000001',
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {"customer_id": "00000000-0000-0000-0000-00000000c001"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-ALLOC-1', 'Allocation SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000501"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO preorders (
                preorder_id,
                tenant_id,
                preorder_code,
                customer_id,
                product_sku_id,
                committed_qty,
                allocated_qty,
                delivered_qty,
                cancelled_qty,
                remaining_qty,
                delivery_cadence,
                status,
                start_date,
                updated_at
            ) VALUES (
                :preorder_id,
                'default',
                'DT-ALLOC-001',
                :customer_id,
                :product_sku_id,
                10,
                0,
                0,
                0,
                10,
                'weekly',
                'active',
                CURRENT_DATE,
                now()
            )
            """
        ),
        {
            "preorder_id": "00000000-0000-0000-0000-000000000601",
            "customer_id": "00000000-0000-0000-0000-00000000c001",
            "product_sku_id": "00000000-0000-0000-0000-000000000501",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                tenant_id,
                lot_code,
                product_sku_id,
                source_type,
                source_ref_id,
                harvest_or_production_date,
                actual_qty,
                available_qty,
                reserved_qty,
                released_qty,
                status,
                updated_at
            ) VALUES (
                :lot_id,
                'default',
                'LOT-ALLOC-001',
                :product_sku_id,
                'processing_batch',
                'PROC-ALLOC-001',
                now(),
                10,
                10,
                0,
                10,
                'released',
                now()
            )
            """
        ),
        {
            "lot_id": "00000000-0000-0000-0000-000000000701",
            "product_sku_id": "00000000-0000-0000-0000-000000000501",
        },
    )

    created = order_service.create_order(
        CreateOrderRequest(
            customerId="00000000-0000-0000-0000-00000000c001",
            channel="web",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="00000000-0000-0000-0000-000000000501",
                    orderedQty=4,
                    unit="kg",
                    sourcePreorderId="00000000-0000-0000-0000-000000000601",
                )
            ],
            meta=Meta(correlationId="corr-pg-order-create", idempotencyKey="idem-pg-order-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=Meta(correlationId="corr-pg-order-confirm", idempotencyKey="idem-pg-order-confirm")),
    )
    allocated = order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000701", allocatedQty=4)
            ],
            meta=Meta(correlationId="corr-pg-order-allocate", idempotencyKey="idem-pg-order-allocate"),
        ),
    )

    preorder_after_allocate = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000601"},
    ).mappings().one()
    assert float(preorder_after_allocate["allocated_qty"]) == 4.0
    assert float(preorder_after_allocate["remaining_qty"]) == 6.0

    adjusted = order_service.adjust_allocation(
        order_id,
        allocated.allocations[0].allocationId,
        AdjustAllocationRequest(
            newAllocatedQty=2,
            reason="customer_reduced_qty",
            meta=Meta(correlationId="corr-pg-order-adjust", idempotencyKey="idem-pg-order-adjust"),
        ),
    )
    assert adjusted.orderStatus == "partially_allocated"
    assert adjusted.allocation.allocatedQty == 2

    preorder_after_adjust = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000601"},
    ).mappings().one()
    assert float(preorder_after_adjust["allocated_qty"]) == 2.0
    assert float(preorder_after_adjust["remaining_qty"]) == 8.0

    released = order_service.release_allocation(
        order_id,
        allocated.allocations[0].allocationId,
        ReleaseAllocationRequest(
            reason="lot_reassigned",
            meta=Meta(correlationId="corr-pg-order-release", idempotencyKey="idem-pg-order-release"),
        ),
    )
    assert released.orderStatus == "confirmed"
    assert released.allocation.status == "released"

    order_row = postgres_db_session.execute(
        text("SELECT status FROM sales_orders WHERE order_id = :order_id"),
        {"order_id": order_id},
    ).scalar_one()
    assert order_row == "confirmed"

    line_row = postgres_db_session.execute(
        text("SELECT allocated_qty FROM sales_order_lines WHERE order_line_id = :order_line_id"),
        {"order_line_id": order_line_id},
    ).scalar_one()
    assert float(line_row) == 0.0

    allocation_row = postgres_db_session.execute(
        text("SELECT allocated_qty, status FROM allocations WHERE allocation_id = :allocation_id"),
        {"allocation_id": allocated.allocations[0].allocationId},
    ).mappings().one()
    assert float(allocation_row["allocated_qty"]) == 2.0
    assert allocation_row["status"] == "released"

    lot_row = postgres_db_session.execute(
        text("SELECT available_qty, reserved_qty FROM lots WHERE lot_id = :lot_id"),
        {"lot_id": "00000000-0000-0000-0000-000000000701"},
    ).mappings().one()
    assert float(lot_row["available_qty"]) == 10.0
    assert float(lot_row["reserved_qty"]) == 0.0

    preorder_row = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000601"},
    ).mappings().one()
    assert float(preorder_row["allocated_qty"]) == 0.0
    assert float(preorder_row["remaining_qty"]) == 10.0

    movement_rows = postgres_db_session.execute(
        text(
            """
            SELECT movement_type, qty
            FROM inventory_movements
            WHERE related_order_id = :order_id
            ORDER BY created_at, inventory_movement_id
            """
        ),
        {"order_id": order_id},
    ).mappings().all()
    movement_facts = sorted((row["movement_type"], float(row["qty"])) for row in movement_rows)
    assert movement_facts == [
        ("release_reservation", 2.0),
        ("release_reservation", 2.0),
        ("reserve", 4.0),
    ]


@pytest.mark.postgres_integration
def test_order_cancel_releases_preorder_quota_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(order_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(order_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))

    postgres_db_session.execute(
        text(
            """
            INSERT INTO customers (
                customer_id,
                tenant_id,
                customer_code,
                full_name,
                phone,
                phone_normalized,
                channel_source,
                status,
                tags,
                notes
            ) VALUES (
                :customer_id,
                'default',
                'KH-ALLOC-002',
                'Allocation PG Cancel User',
                '+84900000002',
                '84900000002',
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {"customer_id": "00000000-0000-0000-0000-00000000c002"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-ALLOC-2', 'Allocation Cancel SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000502"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO preorders (
                preorder_id,
                tenant_id,
                preorder_code,
                customer_id,
                product_sku_id,
                committed_qty,
                allocated_qty,
                delivered_qty,
                cancelled_qty,
                remaining_qty,
                delivery_cadence,
                status,
                start_date,
                updated_at
            ) VALUES (
                :preorder_id,
                'default',
                'DT-ALLOC-002',
                :customer_id,
                :product_sku_id,
                10,
                0,
                0,
                0,
                10,
                'weekly',
                'active',
                CURRENT_DATE,
                now()
            )
            """
        ),
        {
            "preorder_id": "00000000-0000-0000-0000-000000000602",
            "customer_id": "00000000-0000-0000-0000-00000000c002",
            "product_sku_id": "00000000-0000-0000-0000-000000000502",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO lots (
                lot_id,
                tenant_id,
                lot_code,
                product_sku_id,
                source_type,
                source_ref_id,
                harvest_or_production_date,
                actual_qty,
                available_qty,
                reserved_qty,
                released_qty,
                status,
                updated_at
            ) VALUES (
                :lot_id,
                'default',
                'LOT-ALLOC-002',
                :product_sku_id,
                'processing_batch',
                'PROC-ALLOC-002',
                now(),
                10,
                10,
                0,
                10,
                'released',
                now()
            )
            """
        ),
        {
            "lot_id": "00000000-0000-0000-0000-000000000702",
            "product_sku_id": "00000000-0000-0000-0000-000000000502",
        },
    )

    created = order_service.create_order(
        CreateOrderRequest(
            customerId="00000000-0000-0000-0000-00000000c002",
            channel="web",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="00000000-0000-0000-0000-000000000502",
                    orderedQty=3,
                    unit="kg",
                    sourcePreorderId="00000000-0000-0000-0000-000000000602",
                )
            ],
            meta=Meta(correlationId="corr-pg-order2-create", idempotencyKey="idem-pg-order2-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=Meta(correlationId="corr-pg-order2-confirm", idempotencyKey="idem-pg-order2-confirm")),
    )
    order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000702", allocatedQty=3)
            ],
            meta=Meta(correlationId="corr-pg-order2-allocate", idempotencyKey="idem-pg-order2-allocate"),
        ),
    )

    preorder_after_allocate = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000602"},
    ).mappings().one()
    assert float(preorder_after_allocate["allocated_qty"]) == 3.0
    assert float(preorder_after_allocate["remaining_qty"]) == 7.0

    order_service.request_cancel_order(
        order_id,
        RequestCancelOrderRequest(
            reason="customer_cancelled",
            meta=Meta(correlationId="corr-pg-order2-request-cancel", idempotencyKey="idem-pg-order2-request-cancel"),
        ),
    )
    order_service.cancel_order(
        order_id,
        CancelOrderRequest(
            reason="customer_cancelled",
            meta=Meta(correlationId="corr-pg-order2-cancel", idempotencyKey="idem-pg-order2-cancel"),
        ),
    )

    preorder_after_cancel = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000602"},
    ).mappings().one()
    assert float(preorder_after_cancel["allocated_qty"]) == 0.0
    assert float(preorder_after_cancel["remaining_qty"]) == 10.0
