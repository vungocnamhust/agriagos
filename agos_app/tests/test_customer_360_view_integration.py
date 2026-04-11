# pyright: reportMissingImports=false
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session


@pytest.mark.postgres_integration
def test_customer_360_view_returns_nested_projection_from_real_postgres(
    postgres_db_session: Session,
) -> None:
    code_suffix = uuid.uuid4().hex[:8]
    customer_id = str(uuid.uuid4())
    preorder_active_id = str(uuid.uuid4())
    preorder_cancelled_id = str(uuid.uuid4())
    order_id = str(uuid.uuid4())
    order_line_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())

    postgres_db_session.execute(
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
                :unit,
                :status
            )
            """
        ),
        {
            "product_sku_id": sku_id,
            "sku_code": f"SKU-TEST-{code_suffix}",
            "sku_name": "Test Rice",
            "unit": "kg",
            "status": "active",
        },
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO customers (
                customer_id,
                customer_code,
                full_name,
                phone,
                phone_normalized,
                channel_source,
                default_address,
                district,
                province,
                status,
                tags,
                notes,
                last_order_at
            ) VALUES (
                CAST(:customer_id AS uuid),
                :customer_code,
                :full_name,
                :phone,
                :phone_normalized,
                :channel_source,
                :default_address,
                :district,
                :province,
                :status,
                CAST(:tags AS jsonb),
                :notes,
                now()
            )
            """
        ),
        {
            "customer_id": customer_id,
            "customer_code": f"KH-IT-{code_suffix}",
            "full_name": "Integration Customer",
            "phone": f"0900{customer_id.replace('-', '')[:6]}",
            "phone_normalized": f"0900{customer_id.replace('-', '')[:6]}",
            "channel_source": "zalo",
            "default_address": "Da Lat",
            "district": "Ward 1",
            "province": "Lam Dong",
            "status": "active",
            "tags": '["vip","integration"]',
            "notes": "projection test",
        },
    )
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
                :preference_type,
                :preference_value,
                :source,
                :confidence_level
            )
            """
        ),
        {
            "customer_id": customer_id,
            "preference_type": "pack_size",
            "preference_value": "5kg",
            "source": "human",
            "confidence_level": 0.900,
        },
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
                remaining_qty,
                status
            ) VALUES
            (
                CAST(:preorder_active_id AS uuid),
                'DT-IT-002',
                CAST(:customer_id AS uuid),
                CAST(:product_sku_id AS uuid),
                20,
                5,
                2,
                18,
                'active'
            ),
            (
                CAST(:preorder_cancelled_id AS uuid),
                'DT-IT-001',
                CAST(:customer_id AS uuid),
                CAST(:product_sku_id AS uuid),
                10,
                0,
                0,
                10,
                'cancelled'
            )
            """
        ),
        {
            "preorder_active_id": preorder_active_id,
            "preorder_cancelled_id": preorder_cancelled_id,
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
                note,
                created_by,
                source_preorder_flag,
                status,
                payment_status
            ) VALUES (
                CAST(:order_id AS uuid),
                :order_code,
                CAST(:customer_id AS uuid),
                :channel,
                now() + interval '2 day',
                :shipping_address,
                :note,
                :created_by,
                :source_preorder_flag,
                :status,
                :payment_status
            )
            """
        ),
        {
            "order_id": order_id,
            "order_code": f"ORD-IT-{code_suffix}",
            "customer_id": customer_id,
            "channel": "zalo",
            "shipping_address": "Da Lat",
            "note": "integration order",
            "created_by": "tester",
            "source_preorder_flag": True,
            "status": "confirmed",
            "payment_status": "unpaid",
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
                5,
                2,
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
            "source_preorder_id": preorder_active_id,
        },
    )

    row = postgres_db_session.execute(
        text(
            """
            SELECT customer, active_preorders, recent_orders, preferences
            FROM customer_360_view
            WHERE customer_id = CAST(:customer_id AS uuid)
            """
        ),
        {"customer_id": customer_id},
    ).mappings().first()

    assert row is not None
    assert row["customer"]["customerId"] == customer_id
    assert row["customer"]["customerCode"] == f"KH-IT-{code_suffix}"
    assert row["customer"]["fullName"] == "Integration Customer"
    assert row["customer"]["tags"] == ["vip", "integration"]

    assert [item["preorderCode"] for item in row["active_preorders"]] == ["DT-IT-002"]
    preorder = row["active_preorders"][0]
    assert preorder["status"] == "active"
    assert preorder["committedQty"] == 20
    assert preorder["allocatedQty"] == 5
    assert preorder["deliveredQty"] == 2
    assert preorder["remainingQty"] == 18

    assert [item["orderCode"] for item in row["recent_orders"]] == [f"ORD-IT-{code_suffix}"]
    assert row["recent_orders"][0]["lines"][0]["orderLineId"] == order_line_id
    assert row["recent_orders"][0]["lines"][0]["status"] == "allocated"

    assert row["preferences"] == [
        {
            "preferenceType": "pack_size",
            "preferenceValue": "5kg",
            "confidenceLevel": 0.9,
        }
    ]