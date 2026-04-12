from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.orders import (
    AllocateItem,
    AllocateOrderRequest,
    AdjustAllocationRequest,
    AllocationMutationResponse,
    CancelOrderRequest,
    ConfirmOrderRequest,
    CreateOrderLineRequest,
    CreateOrderRequest,
    DeliverOrderRequest,
    DeliveredQtyItem,
    PackOrderRequest,
    PackQtyItem,
    ShipOrderRequest,
    RequestCancelOrderRequest,
    ReleaseAllocationRequest,
)
from app.services import orders
from app.store import _db, memory
from app.models.enums import LotStatus, PreorderStatus


@dataclass
class FakeSession:
    statements: list[str] = field(default_factory=list)
    commit_count: int = 0
    rollback_count: int = 0
    close_count: int = 0

    def execute(self, statement, _params=None):  # noqa: ANN001
        self.statements.append(str(statement))
        return object()

    def commit(self) -> None:
        self.commit_count += 1

    def rollback(self) -> None:
        self.rollback_count += 1

    def close(self) -> None:
        self.close_count += 1


def test_create_order_postgres_path_uses_single_transaction(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_session = FakeSession()
    session_factory_calls = {"count": 0}

    def session_factory() -> FakeSession:
        session_factory_calls["count"] += 1
        return fake_session

    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(orders.postgres_sync, "customer_exists", lambda customer_id: True)
    monkeypatch.setattr(orders, "_new_order_code", lambda: "ORD-TEST-001")
    monkeypatch.setattr(orders, "check_idempotency", lambda key: None)
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "SessionLocal", session_factory)

    response = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[CreateOrderLineRequest(productSkuId="sku-1", orderedQty=3, unit="kg")],
            meta=Meta(correlationId="corr-order", idempotencyKey="idem-order"),
        )
    )

    assert response.data.orderCode == "ORD-TEST-001"
    assert session_factory_calls["count"] == 1
    assert fake_session.commit_count == 1
    assert fake_session.rollback_count == 0
    assert fake_session.close_count == 1
    sql = "\n".join(fake_session.statements)
    assert "INSERT INTO sales_orders" in sql
    assert "INSERT INTO domain_events" in sql
    assert "INSERT INTO audit_logs" in sql
    assert "INSERT INTO idempotency_records" in sql


def test_confirm_order_missing_aggregate_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        orders.confirm_order("missing-order", ConfirmOrderRequest(meta=Meta(correlationId="corr-confirm")))

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "order.confirm"
    assert memory.list_audit_logs()[-1]["targetId"] == "missing-order"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "order_not_found"


def test_allocate_order_missing_lot_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[CreateOrderLineRequest(productSkuId="sku-1", orderedQty=2, unit="kg")],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())

    with pytest.raises(HTTPException) as exc_info:
        orders.allocate_order(
            created.data.orderId,
            AllocateOrderRequest(
                allocations=[
                    AllocateItem(
                        orderLineId=created.data.lines[0].orderLineId,
                        lotId="missing-lot",
                        allocatedQty=1,
                    )
                ],
                meta=Meta(correlationId="corr-allocate"),
            ),
        )

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "order.allocate"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "lot_not_found"
    assert memory.list_audit_logs()[-1]["metadata"]["lotId"] == "missing-lot"


def _seed_released_lot(*, lot_id: str, available_qty: float) -> None:
    memory.save_lot(
        lot_id,
        {
            "lotId": lot_id,
            "status": LotStatus.released.value,
            "availableQty": available_qty,
            "reservedQty": 0.0,
            "releasedQty": available_qty,
        },
    )


def _seed_preorder(*, preorder_id: str, remaining_qty: float) -> None:
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-TEST-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": remaining_qty,
            "allocatedQty": 0.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": remaining_qty,
            "deliveryCadence": "weekly",
            "status": PreorderStatus.active.value,
            "adjustmentHistory": [],
        },
    )


def test_allocate_order_rejects_aggregate_overflow_on_same_lot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(productSkuId="sku-1", orderedQty=3, unit="kg"),
                CreateOrderLineRequest(productSkuId="sku-1", orderedQty=3, unit="kg"),
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)

    with pytest.raises(HTTPException) as exc_info:
        orders.allocate_order(
            created.data.orderId,
            AllocateOrderRequest(
                allocations=[
                    AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=3),
                    AllocateItem(orderLineId=created.data.lines[1].orderLineId, lotId="lot-1", allocatedQty=3),
                ],
                meta=Meta(correlationId="corr-aggregate-lot-overflow"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "insufficient_lot_qty"
    lot = memory.get_lot("lot-1")
    assert lot is not None
    assert lot["availableQty"] == 5
    assert lot["reservedQty"] == 0


def test_allocate_order_rejects_total_line_allocation_above_ordered_qty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[CreateOrderLineRequest(productSkuId="sku-1", orderedQty=2, unit="kg")],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)
    _seed_released_lot(lot_id="lot-2", available_qty=5)

    with pytest.raises(HTTPException) as exc_info:
        orders.allocate_order(
            created.data.orderId,
            AllocateOrderRequest(
                allocations=[
                    AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=1.5),
                    AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-2", allocatedQty=1.0),
                ],
                meta=Meta(correlationId="corr-line-overflow"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "order_line_qty_exceeded"
    order_record = memory.get_order(created.data.orderId)
    assert order_record is not None
    assert order_record["lines"][0]["allocatedQty"] == 0


def test_allocate_order_rejects_preorder_quota_overflow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    _seed_preorder(preorder_id="preorder-1", remaining_qty=1)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=2,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)

    with pytest.raises(HTTPException) as exc_info:
        orders.allocate_order(
            created.data.orderId,
            AllocateOrderRequest(
                allocations=[
                    AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=2)
                ],
                meta=Meta(correlationId="corr-preorder-overflow"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "preorder_quota_exceeded"
    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 0
    assert preorder["remainingQty"] == 1


def test_allocate_order_records_reserve_movement_and_updates_preorder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    _seed_preorder(preorder_id="preorder-1", remaining_qty=5)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=2,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)

    response = orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=1.5)
            ],
            meta=Meta(correlationId="corr-reserve-success"),
        ),
    )

    assert response.orderId == created.data.orderId
    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 1.5
    assert preorder["remainingQty"] == 3.5

    lot = memory.get_lot("lot-1")
    assert lot is not None
    assert lot["availableQty"] == 3.5
    assert lot["reservedQty"] == 1.5

    movement = memory.list_inventory_movements()[-1]
    assert movement["movementType"] == "reserve"
    assert movement["lotId"] == "lot-1"
    assert movement["qty"] == 1.5
    assert movement["relatedOrderId"] == created.data.orderId
    assert movement["relatedOrderLineId"] == created.data.lines[0].orderLineId


def test_cancel_order_releases_allocation_and_records_release_movement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    _seed_preorder(preorder_id="preorder-1", remaining_qty=5)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=2,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)
    orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=1.5)
            ],
            meta=Meta(correlationId="corr-allocate-before-cancel"),
        ),
    )
    orders.request_cancel_order(
        created.data.orderId,
        RequestCancelOrderRequest(
            reason="customer_changed_mind",
            meta=Meta(correlationId="corr-request-cancel-order"),
        ),
    )

    orders.cancel_order(
        created.data.orderId,
        CancelOrderRequest(reason="customer_changed_mind", meta=Meta(correlationId="corr-cancel-order")),
    )

    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 0.0
    assert preorder["remainingQty"] == 5.0

    lot = memory.get_lot("lot-1")
    assert lot is not None
    assert lot["availableQty"] == 5.0
    assert lot["reservedQty"] == 0.0

    movements = memory.list_inventory_movements()
    assert [movement["movementType"] for movement in movements[-2:]] == ["reserve", "release_reservation"]

    released_event = next(event for event in memory.list_events() if event["eventName"] == "allocation.released")
    assert released_event["payload"]["lotId"] == "lot-1"
    assert released_event["payload"]["releasedQty"] == 1.5

    allocations = memory.get_allocations(created.data.orderId)
    assert allocations[0]["status"] == "cancelled"


def test_adjust_allocation_rebalances_inventory_and_sets_partial_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    _seed_preorder(preorder_id="preorder-1", remaining_qty=8)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=4,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=10)
    allocated = orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=4)
            ],
            meta=Meta(correlationId="corr-adjust-seed"),
        ),
    )

    response = orders.adjust_allocation(
        created.data.orderId,
        allocated.allocations[0].allocationId,
        AdjustAllocationRequest(
            newAllocatedQty=2,
            reason="customer_reduced_qty",
            meta=Meta(correlationId="corr-adjust-allocation"),
        ),
    )

    assert isinstance(response, AllocationMutationResponse)
    assert response.orderStatus == "partially_allocated"
    assert response.allocation.allocatedQty == 2
    assert response.allocation.status == "active"

    lot = memory.get_lot("lot-1")
    assert lot is not None
    assert lot["availableQty"] == 8
    assert lot["reservedQty"] == 2

    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 2
    assert preorder["remainingQty"] == 6

    adjusted_event = next(event for event in memory.list_events() if event["eventName"] == "allocation.adjusted")
    assert adjusted_event["payload"]["oldQty"] == 4
    assert adjusted_event["payload"]["newQty"] == 2


def test_release_allocation_returns_order_to_confirmed_and_marks_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    _seed_preorder(preorder_id="preorder-1", remaining_qty=5)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=2,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=5)
    allocated = orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=2)
            ],
            meta=Meta(correlationId="corr-release-seed"),
        ),
    )

    response = orders.release_allocation(
        created.data.orderId,
        allocated.allocations[0].allocationId,
        ReleaseAllocationRequest(
            reason="lot_reassigned",
            meta=Meta(correlationId="corr-release-allocation"),
        ),
    )

    assert response.orderStatus == "confirmed"
    assert response.allocation.status == "released"
    assert response.allocation.allocatedQty == 2

    lot = memory.get_lot("lot-1")
    assert lot is not None
    assert lot["availableQty"] == 5
    assert lot["reservedQty"] == 0

    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 0
    assert preorder["remainingQty"] == 5


def test_pack_order_sets_partially_packed_when_actual_qty_is_short(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[CreateOrderLineRequest(productSkuId="sku-1", orderedQty=4, unit="kg")],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=10)
    orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=4)
            ],
            meta=Meta(correlationId="corr-pack-seed"),
        ),
    )

    response = orders.pack_order(
        created.data.orderId,
        PackOrderRequest(
            packedQtySummary=[PackQtyItem(orderLineId=created.data.lines[0].orderLineId, packedQty=2)],
            meta=Meta(correlationId="corr-pack-partial"),
        ),
    )

    assert response.data.status == "partially_packed"
    assert response.data.lines[0].packedQty == 2

    packed_event = next(event for event in memory.list_events() if event["eventName"] == "order.partially_packed")
    assert packed_event["payload"]["orderId"] == created.data.orderId


def test_deliver_order_consumes_preorder_using_delivered_delta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {"customerId": "customer-1", "customerCode": "KH-001", "fullName": "Alice", "phone": "0901"},
    )
    _seed_preorder(preorder_id="preorder-1", remaining_qty=20)
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[
                CreateOrderLineRequest(
                    productSkuId="sku-1",
                    orderedQty=15,
                    unit="kg",
                    sourcePreorderId="preorder-1",
                )
            ],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=20)
    orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=15)
            ],
            meta=Meta(correlationId="corr-deliver-seed"),
        ),
    )
    orders.pack_order(
        created.data.orderId,
        PackOrderRequest(
            packedQtySummary=[PackQtyItem(orderLineId=created.data.lines[0].orderLineId, packedQty=15)],
            meta=Meta(correlationId="corr-pack-full"),
        ),
    )
    orders.ship_order(
        created.data.orderId,
        ShipOrderRequest(carrier="gha", trackingRef="TRK-1", shippedAt="2026-04-12T10:00:00Z", meta=Meta(correlationId="corr-ship")),
    )

    response = orders.deliver_order(
        created.data.orderId,
        DeliverOrderRequest(
            deliveredQtySummary=[
                DeliveredQtyItem(orderLineId=created.data.lines[0].orderLineId, deliveredQty=12)
            ],
            deliveredAt="2026-04-12T11:00:00Z",
            proofRef="proof-1",
            meta=Meta(correlationId="corr-deliver"),
        ),
    )

    assert response.data.status == "partially_delivered"
    assert response.data.lines[0].deliveredQty == 12

    preorder = memory.get_preorder("preorder-1")
    assert preorder is not None
    assert preorder["allocatedQty"] == 3
    assert preorder["deliveredQty"] == 12
    assert preorder["remainingQty"] == 5

    customer = memory.get_customer("customer-1")
    assert customer is not None
    assert customer["lastOrderAt"] == "2026-04-12T11:00:00Z"

    consumed_event = next(event for event in memory.list_events() if event["eventName"] == "preorder.quota_consumed")
    assert consumed_event["payload"]["consumedQty"] == 12

    purchase_event = next(event for event in memory.list_events() if event["eventName"] == "customer.last_purchase_updated")
    assert purchase_event["payload"]["lastOrderId"] == created.data.orderId


def test_deliver_order_allows_partial_then_final_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(orders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer(
        "customer-1",
        {"customerId": "customer-1", "customerCode": "KH-001", "fullName": "Alice", "phone": "0901"},
    )
    created = orders.create_order(
        CreateOrderRequest(
            customerId="customer-1",
            channel="direct",
            lines=[CreateOrderLineRequest(productSkuId="sku-1", orderedQty=10, unit="kg")],
        )
    )
    orders.confirm_order(created.data.orderId, ConfirmOrderRequest())
    _seed_released_lot(lot_id="lot-1", available_qty=10)
    orders.allocate_order(
        created.data.orderId,
        AllocateOrderRequest(
            allocations=[
                AllocateItem(orderLineId=created.data.lines[0].orderLineId, lotId="lot-1", allocatedQty=10)
            ],
            meta=Meta(correlationId="corr-deliver-seed-2"),
        ),
    )
    orders.pack_order(
        created.data.orderId,
        PackOrderRequest(
            packedQtySummary=[PackQtyItem(orderLineId=created.data.lines[0].orderLineId, packedQty=10)],
            meta=Meta(correlationId="corr-pack-2"),
        ),
    )
    orders.ship_order(
        created.data.orderId,
        ShipOrderRequest(carrier="gha", trackingRef="TRK-2", shippedAt="2026-04-12T10:00:00Z", meta=Meta(correlationId="corr-ship-2")),
    )

    partial = orders.deliver_order(
        created.data.orderId,
        DeliverOrderRequest(
            deliveredQtySummary=[
                DeliveredQtyItem(orderLineId=created.data.lines[0].orderLineId, deliveredQty=4)
            ],
            deliveredAt="2026-04-12T11:00:00Z",
            meta=Meta(correlationId="corr-deliver-partial-2"),
        ),
    )
    assert partial.data.status == "partially_delivered"

    final = orders.deliver_order(
        created.data.orderId,
        DeliverOrderRequest(
            deliveredQtySummary=[
                DeliveredQtyItem(orderLineId=created.data.lines[0].orderLineId, deliveredQty=10)
            ],
            deliveredAt="2026-04-12T12:00:00Z",
            meta=Meta(correlationId="corr-deliver-final-2"),
        ),
    )

    assert final.data.status == "delivered"
    assert final.data.lines[0].deliveredQty == 10