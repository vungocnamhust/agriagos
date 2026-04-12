from __future__ import annotations

import pytest

from app.services import audit


def test_order_reason_code_registry_accepts_known_reason_code() -> None:
    normalized = audit.standardize_audit_payload(
        target_type="Order",
        action_name="order.allocate",
        decision="denied",
        reason_code="insufficient_lot_qty",
        before_snapshot={"orderId": "order-1", "status": "confirmed", "note": "drop me", "lines": []},
        after_snapshot=None,
        metadata=None,
    )

    assert normalized["reason_code"] == "insufficient_lot_qty"


def test_order_reason_code_registry_rejects_unknown_reason_code() -> None:
    with pytest.raises(ValueError) as exc_info:
        audit.standardize_audit_payload(
            target_type="Order",
            action_name="order.allocate",
            decision="denied",
            reason_code="not_registered",
            before_snapshot={"orderId": "order-1", "status": "confirmed", "lines": []},
            after_snapshot=None,
            metadata=None,
        )

    assert "Unknown audit reason code" in str(exc_info.value)


def test_lot_reason_code_registry_accepts_known_reason_code() -> None:
    normalized = audit.standardize_audit_payload(
        target_type="Lot",
        action_name="lot.release",
        decision="failed",
        reason_code="persistence_failed",
        before_snapshot={"lotId": "lot-1", "status": "harvested"},
        after_snapshot=None,
        metadata=None,
    )

    assert normalized["reason_code"] == "persistence_failed"


def test_sensitive_snapshot_policy_reduces_order_snapshot_shape() -> None:
    normalized = audit.standardize_audit_payload(
        target_type="Order",
        action_name="order.confirm",
        decision="allowed",
        reason_code=None,
        before_snapshot={
            "orderId": "order-1",
            "orderCode": "ORD-001",
            "status": "draft",
            "note": "internal note",
            "paymentIntent": "cash",
            "lines": [
                {
                    "orderLineId": "line-1",
                    "productSkuId": "sku-1",
                    "orderedQty": 2,
                    "allocatedQty": 0,
                    "packedQty": 0,
                    "deliveredQty": 0,
                    "unit": "kg",
                    "status": "open",
                    "sourcePreorderId": "pre-1",
                    "temporaryFlag": True,
                }
            ],
        },
        after_snapshot={
            "orderId": "order-1",
            "orderCode": "ORD-001",
            "status": "confirmed",
            "note": "internal note",
            "paymentIntent": "cash",
            "lines": [
                {
                    "orderLineId": "line-1",
                    "productSkuId": "sku-1",
                    "orderedQty": 2,
                    "allocatedQty": 0,
                    "packedQty": 0,
                    "deliveredQty": 0,
                    "unit": "kg",
                    "status": "open",
                    "sourcePreorderId": "pre-1",
                    "temporaryFlag": True,
                }
            ],
        },
        metadata=None,
    )

    assert normalized["before_snapshot"] == {
        "orderId": "order-1",
        "orderCode": "ORD-001",
        "status": "draft",
        "lines": [
            {
                "orderLineId": "line-1",
                "productSkuId": "sku-1",
                "orderedQty": 2,
                "allocatedQty": 0,
                "packedQty": 0,
                "deliveredQty": 0,
                "unit": "kg",
                "status": "open",
                "sourcePreorderId": "pre-1",
            }
        ],
    }
    assert normalized["after_snapshot"]["status"] == "confirmed"
    assert "note" not in normalized["after_snapshot"]
    assert "temporaryFlag" not in normalized["after_snapshot"]["lines"][0]


def test_sensitive_snapshot_policy_reduces_preorder_snapshot_shape() -> None:
    normalized = audit.standardize_audit_payload(
        target_type="Preorder",
        action_name="preorder.adjust",
        decision="allowed",
        reason_code=None,
        before_snapshot={
            "preorderId": "pre-1",
            "preorderCode": "DT-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10,
            "allocatedQty": 2,
            "deliveredQty": 1,
            "remainingQty": 7,
            "cancelledQty": 0,
            "status": "active",
            "deliveryCadence": "weekly",
            "notes": "drop me",
            "adjustmentHistory": [{"oldCommittedQty": 8, "newCommittedQty": 10, "reason": "resize", "changedAt": "2026-04-12T10:00:00Z", "actorId": "sales-1", "internal": "x"}],
        },
        after_snapshot={
            "preorderId": "pre-1",
            "preorderCode": "DT-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 12,
            "allocatedQty": 2,
            "deliveredQty": 1,
            "remainingQty": 9,
            "cancelledQty": 0,
            "status": "active",
            "deliveryCadence": "weekly",
            "notes": "drop me",
            "adjustmentHistory": [{"oldCommittedQty": 10, "newCommittedQty": 12, "reason": "resize", "changedAt": "2026-04-12T11:00:00Z", "actorId": "sales-1", "internal": "x"}],
        },
        metadata=None,
    )

    assert normalized["before_snapshot"]["committedQty"] == 10
    assert normalized["after_snapshot"]["committedQty"] == 12
    assert "notes" not in normalized["after_snapshot"]
    assert normalized["after_snapshot"]["adjustmentHistory"][0] == {
        "oldCommittedQty": 10,
        "newCommittedQty": 12,
        "reason": "resize",
        "changedAt": "2026-04-12T11:00:00Z",
        "actorId": "sales-1",
    }


def test_sensitive_snapshot_policy_reduces_lot_snapshot_shape() -> None:
    normalized = audit.standardize_audit_payload(
        target_type="Lot",
        action_name="lot.block",
        decision="allowed",
        reason_code=None,
        before_snapshot={
            "lotId": "lot-1",
            "lotCode": "LOT-001",
            "status": "released",
            "actualQty": 10,
            "availableQty": 6,
            "reservedQty": 2,
            "releasedQty": 8,
            "unit": "kg",
            "qualityStatus": "passed",
            "attachments": ["a.jpg"],
            "qualityNote": "internal",
        },
        after_snapshot={
            "lotId": "lot-1",
            "lotCode": "LOT-001",
            "status": "blocked",
            "actualQty": 10,
            "availableQty": 0,
            "reservedQty": 0,
            "releasedQty": 0,
            "unit": "kg",
            "qualityStatus": "blocked",
            "attachments": ["a.jpg"],
            "qualityNote": "internal",
        },
        metadata=None,
    )

    assert normalized["before_snapshot"] == {
        "lotId": "lot-1",
        "lotCode": "LOT-001",
        "actualQty": 10,
        "availableQty": 6,
        "reservedQty": 2,
        "releasedQty": 8,
        "unit": "kg",
        "status": "released",
        "qualityStatus": "passed",
    }
    assert normalized["after_snapshot"]["status"] == "blocked"
    assert "attachments" not in normalized["after_snapshot"]
    assert "qualityNote" not in normalized["after_snapshot"]