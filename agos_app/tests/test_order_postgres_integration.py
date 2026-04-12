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
    DeliverOrderRequest,
    DeliveredQtyItem,
    FailDeliveryRequest,
    PackOrderRequest,
    PackQtyItem,
    ReleaseAllocationRequest,
    RequestCancelOrderRequest,
    ShipOrderRequest,
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


def _admin_meta(correlation_id: str, idempotency_key: str) -> Meta:
    return Meta(
        correlationId=correlation_id,
        idempotencyKey=idempotency_key,
        actorId="admin-pg-1",
        actorRole="admin",
    )


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
            meta=_admin_meta("corr-pg-order-create", "idem-pg-order-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=_admin_meta("corr-pg-order-confirm", "idem-pg-order-confirm")),
    )
    allocated = order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000701", allocatedQty=4)
            ],
            meta=_admin_meta("corr-pg-order-allocate", "idem-pg-order-allocate"),
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
            meta=_admin_meta("corr-pg-order-adjust", "idem-pg-order-adjust"),
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
            meta=_admin_meta("corr-pg-order-release", "idem-pg-order-release"),
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
            meta=_admin_meta("corr-pg-order2-create", "idem-pg-order2-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=_admin_meta("corr-pg-order2-confirm", "idem-pg-order2-confirm")),
    )
    order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000702", allocatedQty=3)
            ],
            meta=_admin_meta("corr-pg-order2-allocate", "idem-pg-order2-allocate"),
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
            meta=_admin_meta("corr-pg-order2-request-cancel", "idem-pg-order2-request-cancel"),
        ),
    )
    order_service.cancel_order(
        order_id,
        CancelOrderRequest(
            reason="customer_cancelled",
            meta=_admin_meta("corr-pg-order2-cancel", "idem-pg-order2-cancel"),
        ),
    )

    preorder_after_cancel = postgres_db_session.execute(
        text("SELECT allocated_qty, remaining_qty FROM preorders WHERE preorder_id = :preorder_id"),
        {"preorder_id": "00000000-0000-0000-0000-000000000602"},
    ).mappings().one()
    assert float(preorder_after_cancel["allocated_qty"]) == 0.0
    assert float(preorder_after_cancel["remaining_qty"]) == 10.0


@pytest.mark.postgres_integration
def test_fulfillment_metadata_and_last_purchase_persist_on_postgres_path(
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
                'KH-FULL-001',
                'Fulfillment PG User',
                '+84987654321',
                '84987654321',
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {"customer_id": "00000000-0000-0000-0000-00000000c003"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-FULL-1', 'Fulfillment SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000503"},
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
                'LOT-FULL-001',
                :product_sku_id,
                'processing_batch',
                'PROC-FULL-001',
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
            "lot_id": "00000000-0000-0000-0000-000000000703",
            "product_sku_id": "00000000-0000-0000-0000-000000000503",
        },
    )

    created = order_service.create_order(
        CreateOrderRequest(
            customerId="00000000-0000-0000-0000-00000000c003",
            channel="web",
            lines=[CreateOrderLineRequest(productSkuId="00000000-0000-0000-0000-000000000503", orderedQty=6, unit="kg")],
            meta=_admin_meta("corr-pg-full-create", "idem-pg-full-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=_admin_meta("corr-pg-full-confirm", "idem-pg-full-confirm")),
    )
    order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000703", allocatedQty=6)
            ],
            meta=_admin_meta("corr-pg-full-allocate", "idem-pg-full-allocate"),
        ),
    )
    order_service.pack_order(
        order_id,
        PackOrderRequest(
            packedQtySummary=[PackQtyItem(orderLineId=order_line_id, packedQty=6)],
            meta=_admin_meta("corr-pg-full-pack", "idem-pg-full-pack"),
        ),
    )
    order_service.ship_order(
        order_id,
        ShipOrderRequest(
            carrier="gha",
            trackingRef="TRK-PG-1",
            shippedAt="2026-04-12T10:00:00Z",
            meta=_admin_meta("corr-pg-full-ship", "idem-pg-full-ship"),
        ),
    )
    delivered = order_service.deliver_order(
        order_id,
        DeliverOrderRequest(
            deliveredQtySummary=[DeliveredQtyItem(orderLineId=order_line_id, deliveredQty=4)],
            deliveredAt="2026-04-12T11:00:00Z",
            proofRef="proof-pg-1",
            meta=_admin_meta("corr-pg-full-deliver", "idem-pg-full-deliver"),
        ),
    )

    assert delivered.data.status == "partially_delivered"

    order_row = postgres_db_session.execute(
        text(
            """
            SELECT status, carrier, tracking_ref, shipped_at, delivered_at, proof_ref
            FROM sales_orders
            WHERE order_id = :order_id
            """
        ),
        {"order_id": order_id},
    ).mappings().one()
    assert order_row["status"] == "partially_delivered"
    assert order_row["carrier"] == "gha"
    assert order_row["tracking_ref"] == "TRK-PG-1"
    assert order_row["shipped_at"] is not None
    assert order_row["delivered_at"] is not None
    assert order_row["proof_ref"] == "proof-pg-1"

    line_row = postgres_db_session.execute(
        text("SELECT packed_qty, delivered_qty FROM sales_order_lines WHERE order_line_id = :order_line_id"),
        {"order_line_id": order_line_id},
    ).mappings().one()
    assert float(line_row["packed_qty"]) == 6.0
    assert float(line_row["delivered_qty"]) == 4.0

    customer_row = postgres_db_session.execute(
        text("SELECT last_order_at FROM customers WHERE customer_id = :customer_id"),
        {"customer_id": "00000000-0000-0000-0000-00000000c003"},
    ).mappings().one()
    assert customer_row["last_order_at"] is not None


@pytest.mark.postgres_integration
def test_failed_delivery_persists_failed_status_without_customer_purchase_update(
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
                'KH-FAIL-001',
                'Failed Delivery PG User',
                '+84981234567',
                '84981234567',
                'internal_ui',
                'active',
                '[]'::jsonb,
                null
            )
            """
        ),
        {"customer_id": "00000000-0000-0000-0000-00000000c004"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-FAIL-1', 'Failed Delivery SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000504"},
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
                'LOT-FAIL-001',
                :product_sku_id,
                'processing_batch',
                'PROC-FAIL-001',
                now(),
                6,
                6,
                0,
                6,
                'released',
                now()
            )
            """
        ),
        {
            "lot_id": "00000000-0000-0000-0000-000000000704",
            "product_sku_id": "00000000-0000-0000-0000-000000000504",
        },
    )

    created = order_service.create_order(
        CreateOrderRequest(
            customerId="00000000-0000-0000-0000-00000000c004",
            channel="web",
            lines=[CreateOrderLineRequest(productSkuId="00000000-0000-0000-0000-000000000504", orderedQty=6, unit="kg")],
            meta=_admin_meta("corr-pg-fail-create", "idem-pg-fail-create"),
        )
    )
    order_id = created.data.orderId
    order_line_id = created.data.lines[0].orderLineId

    order_service.confirm_order(
        order_id,
        ConfirmOrderRequest(meta=_admin_meta("corr-pg-fail-confirm", "idem-pg-fail-confirm")),
    )
    order_service.allocate_order(
        order_id,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=order_line_id, lotId="00000000-0000-0000-0000-000000000704", allocatedQty=6)
            ],
            meta=_admin_meta("corr-pg-fail-allocate", "idem-pg-fail-allocate"),
        ),
    )
    order_service.pack_order(
        order_id,
        PackOrderRequest(
            packedQtySummary=[PackQtyItem(orderLineId=order_line_id, packedQty=6)],
            meta=_admin_meta("corr-pg-fail-pack", "idem-pg-fail-pack"),
        ),
    )
    order_service.ship_order(
        order_id,
        ShipOrderRequest(
            carrier="gha",
            trackingRef="TRK-PG-FAIL-1",
            shippedAt="2026-04-12T10:00:00Z",
            meta=_admin_meta("corr-pg-fail-ship", "idem-pg-fail-ship"),
        ),
    )
    failed = order_service.fail_delivery(
        order_id,
        FailDeliveryRequest(
            failureReason="customer_unreachable",
            note="carrier could not complete handoff",
            meta=_admin_meta("corr-pg-fail-deliver", "idem-pg-fail-deliver"),
        ),
    )

    assert failed.data.status == "failed"
    assert failed.data.failureReason == "customer_unreachable"

    order_row = postgres_db_session.execute(
        text("SELECT status, delivered_at, failure_reason FROM sales_orders WHERE order_id = :order_id"),
        {"order_id": order_id},
    ).mappings().one()
    assert order_row["status"] == "failed"
    assert order_row["delivered_at"] is None
    assert order_row["failure_reason"] == "customer_unreachable"

    line_row = postgres_db_session.execute(
        text("SELECT delivered_qty FROM sales_order_lines WHERE order_line_id = :order_line_id"),
        {"order_line_id": order_line_id},
    ).mappings().one()
    assert float(line_row["delivered_qty"]) == 0.0

    customer_row = postgres_db_session.execute(
        text("SELECT last_order_at FROM customers WHERE customer_id = :customer_id"),
        {"customer_id": "00000000-0000-0000-0000-00000000c004"},
    ).mappings().one()
    assert customer_row["last_order_at"] is None
