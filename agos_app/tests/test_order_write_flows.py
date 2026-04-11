from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.orders import (
    AllocateItem,
    AllocateOrderRequest,
    ConfirmOrderRequest,
    CreateOrderLineRequest,
    CreateOrderRequest,
)
from app.services import orders
from app.store import _db, memory


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