from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.orders import ConfirmOrderRequest, CreateOrderLineRequest, CreateOrderRequest
from app.models.enums import PreorderStatus
from app.services import orders
from app.store import memory


def _admin_meta(correlation_id: str) -> Meta:
    return Meta(correlationId=correlation_id, actorId="admin-1", actorRole="admin")


def _seed_preorder(preorder_id: str = "preorder-1") -> str:
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-TEST-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 20.0,
            "allocatedQty": 0.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": 20.0,
            "deliveryCadence": "weekly",
            "status": PreorderStatus.active.value,
            "adjustmentHistory": [],
        },
    )
    return preorder_id


def test_create_order_rejects_invalid_source_preorder_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})

    with pytest.raises(HTTPException) as exc_info:
        orders.create_order(
            CreateOrderRequest(
                customerId="customer-1",
                channel="direct",
                lines=[
                    CreateOrderLineRequest(
                        productSkuId="sku-1",
                        orderedQty=5,
                        unit="kg",
                        sourcePreorderId="missing-preorder-id",
                    )
                ],
                meta=_admin_meta("corr-bad-preorder"),
            )
        )

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Preorder missing-preorder-id not found."
    denied_audit = memory.list_audit_logs()[-1]
    assert denied_audit["actionName"] == "order.create"
    assert denied_audit["reasonCode"] == "source_preorder_not_found"
    assert denied_audit["metadata"]["sourcePreorderId"] == "missing-preorder-id"


def test_create_and_get_order_preserve_line_level_preorder_linkage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    preorder_id = _seed_preorder()

    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=5,
                    unit="kg",
                    sourcePreorderId=preorder_id,
                ),
                CreateOrderLineRequest(
                    productSkuId="sku-2",
                    orderedQty=3,
                    unit="kg",
                ),
            ],
            meta=_admin_meta("corr-create-order"),
        )
    )

    assert created.data.sourcePreorderFlag is True
    assert created.data.lines[0].sourcePreorderId == preorder_id
    assert created.data.lines[1].sourcePreorderId is None

    persisted = memory.get_order(created.data.orderId)
    assert persisted is not None
    assert persisted["sourcePreorderFlag"] is True

    detail = orders.get_order(created.data.orderId, meta=_admin_meta("corr-get-order"))
    assert detail.sourcePreorderFlag is True
    assert detail.lines[0].sourcePreorderId == preorder_id
    assert detail.lines[1].sourcePreorderId is None


def test_confirm_order_preserves_linkage_and_emits_preorder_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    preorder_id = _seed_preorder()

    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=5,
                    unit="kg",
                    sourcePreorderId=preorder_id,
                )
            ],
            meta=_admin_meta("corr-create-linked-order"),
        )
    )

    confirmed = orders.confirm_order(
        created.data.orderId,
        ConfirmOrderRequest(meta=_admin_meta("corr-confirm-linked-order")),
    )

    assert confirmed.data.sourcePreorderFlag is True
    assert confirmed.data.lines[0].sourcePreorderId == preorder_id

    confirmed_event = next(
        event for event in memory.list_events() if event["eventName"] == "order.confirmed"
    )
    assert confirmed_event["payload"]["sourcePreorderFlag"] is True
    assert confirmed_event["payload"]["linkedPreorderIds"] == [preorder_id]


def test_confirm_order_rejects_when_linked_preorder_becomes_unlinkable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    preorder_id = _seed_preorder()

    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=5,
                    unit="kg",
                    sourcePreorderId=preorder_id,
                )
            ],
            meta=_admin_meta("corr-create-revalidate"),
        )
    )

    preorder_record = memory.get_preorder(preorder_id)
    assert preorder_record is not None
    preorder_record["status"] = PreorderStatus.cancelled.value
    memory.save_preorder(preorder_id, preorder_record)

    with pytest.raises(HTTPException) as exc_info:
        orders.confirm_order(
            created.data.orderId,
            ConfirmOrderRequest(meta=_admin_meta("corr-confirm-revalidate")),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == f"Preorder {preorder_id} is not linkable from status cancelled."