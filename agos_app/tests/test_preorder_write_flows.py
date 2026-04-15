from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.enums import PreorderStatus
from app.models.preorders import (
    ActivatePreorderRequest,
    AdjustPreorderRequest,
    CancelPreorderRequest,
    ConfirmPreorderRequest,
    CreatePreorderRequest,
)
from app.services import preorders
from app.store import memory


def test_create_preorder_records_event_audit_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})

    response = preorders.create_preorder(
        CreatePreorderRequest(
            customerId="customer-1",
            productSkuId="sku-1",
            committedQty=12,
            meta=Meta(correlationId="corr-preorder", idempotencyKey="idem-preorder", actorId="sales-1", actorRole="sales"),
        )
    )

    assert memory.get_preorder(response.data.preorderId) is not None
    assert memory.list_events()[-1]["eventName"] == "preorder.placed"
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.create"
    assert memory.get_idempotent_result("idem-preorder")["data"]["preorderId"] == response.data.preorderId
    assert response.data.status == PreorderStatus.draft
    assert response.data.remainingQty == 12


def test_create_preorder_persists_organization_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})
    memory.save_organization("org-1", {"organizationId": "org-1", "name": "Farm Org"})

    response = preorders.create_preorder(
        CreatePreorderRequest(
            customerId="customer-1",
            productSkuId="sku-1",
            committedQty=12,
            organizationId="org-1",
            meta=Meta(correlationId="corr-preorder-org", actorId="sales-1", actorRole="sales"),
        )
    )

    stored = memory.get_preorder(response.data.preorderId)
    assert stored is not None
    assert stored["organizationId"] == "org-1"
    assert response.data.organizationId == "org-1"


def test_adjust_preorder_missing_aggregate_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        preorders.adjust_preorder(
            "missing-preorder",
            AdjustPreorderRequest(
                newCommittedQty=8,
                reason="resize",
                meta=Meta(correlationId="corr-adjust"),
            ),
        )

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.adjust"
    assert memory.list_audit_logs()[-1]["targetId"] == "missing-preorder"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "preorder_not_found"


def test_confirm_and_activate_preorder_emit_events(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-1", {"customerId": "customer-1", "fullName": "Alice"})

    created = preorders.create_preorder(
        CreatePreorderRequest(
            customerId="customer-1",
            productSkuId="sku-1",
            committedQty=12,
            meta=Meta(correlationId="corr-preorder", actorId="sales-1", actorRole="sales"),
        )
    )

    confirmed = preorders.confirm_preorder(
        created.data.preorderId,
        ConfirmPreorderRequest(meta=Meta(correlationId="corr-preorder-confirm", actorId="sales-1", actorRole="sales")),
    )
    activated = preorders.activate_preorder(
        created.data.preorderId,
        ActivatePreorderRequest(meta=Meta(correlationId="corr-preorder-activate", actorId="sales-1", actorRole="sales")),
    )

    assert confirmed.data.status == PreorderStatus.confirmed
    assert activated.data.status == PreorderStatus.active
    assert [event["eventName"] for event in memory.list_events()[-2:]] == [
        "preorder.confirmed",
        "preorder.activated",
    ]


def test_adjust_preorder_recomputes_remaining_qty_using_allocated_and_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-1"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-001",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 3.0,
            "deliveredQty": 2.0,
            "cancelledQty": 0.0,
            "remainingQty": 5.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    response = preorders.adjust_preorder(
        preorder_id,
        AdjustPreorderRequest(
            newCommittedQty=12.0,
            reason="increase quota",
            meta=Meta(correlationId="corr-adjust", actorId="sales-1", actorRole="sales"),
        ),
    )

    assert response.data.remainingQty == 7.0
    detail = preorders.get_preorder(preorder_id, meta=Meta(actorId="sales-1", actorRole="sales"))
    assert detail.adjustmentHistory[0].oldCommittedQty == 10.0
    assert detail.adjustmentHistory[0].newCommittedQty == 12.0


def test_adjust_preorder_rejects_new_committed_qty_below_allocated_and_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-2"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-002",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 3.0,
            "deliveredQty": 2.0,
            "cancelledQty": 0.0,
            "remainingQty": 5.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.adjust_preorder(
            preorder_id,
            AdjustPreorderRequest(
                newCommittedQty=4.0,
                reason="invalid shrink",
                meta=Meta(correlationId="corr-adjust-reject", actorId="sales-1", actorRole="sales"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "committed_qty_below_reserved_and_delivered"


def test_adjust_preorder_rejects_new_committed_qty_below_cancelled_allocated_and_delivered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-2b"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-002B",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 1.0,
            "deliveredQty": 2.0,
            "cancelledQty": 3.0,
            "remainingQty": 4.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.adjust_preorder(
            preorder_id,
            AdjustPreorderRequest(
                newCommittedQty=5.0,
                reason="invalid shrink",
                meta=Meta(correlationId="corr-adjust-reject-cancelled", actorId="sales-1", actorRole="sales"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "committed_qty_below_reserved_and_delivered"


def test_cancel_preorder_blocks_when_allocated_qty_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-3"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-003",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 1.0,
            "deliveredQty": 2.0,
            "cancelledQty": 0.0,
            "remainingQty": 7.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.cancel_preorder(
            preorder_id,
            CancelPreorderRequest(
                reason="customer changed mind",
                meta=Meta(correlationId="corr-cancel", actorId="sales-1", actorRole="sales"),
            ),
        )

    assert exc_info.value.status_code == 422
    assert memory.list_audit_logs()[-1]["reasonCode"] == "preorder_has_allocations"


def test_cancel_preorder_consumes_outstanding_quota_and_emits_event(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-4"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-004",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 0.0,
            "deliveredQty": 2.0,
            "cancelledQty": 0.0,
            "remainingQty": 8.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    response = preorders.cancel_preorder(
        preorder_id,
        CancelPreorderRequest(
            reason="customer changed mind",
            meta=Meta(correlationId="corr-cancel-ok", actorId="sales-1", actorRole="sales"),
        ),
    )

    assert response.data.status == PreorderStatus.cancelled
    assert response.data.cancelledQty == 8.0
    assert response.data.remainingQty == 0.0
    assert memory.list_events()[-1]["eventName"] == "preorder.cancelled"


def test_create_preorder_denies_missing_actor_role_and_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    memory.save_customer("customer-2", {"customerId": "customer-2", "fullName": "Bob"})

    with pytest.raises(HTTPException) as exc_info:
        preorders.create_preorder(
            CreatePreorderRequest(
                customerId="customer-2",
                productSkuId="sku-1",
                committedQty=6,
                meta=Meta(correlationId="corr-preorder-no-role", actorId="actor-1"),
            )
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Actor is not allowed to create preorders."
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.create"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_preorder_write"


def test_get_preorder_denies_viewer_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-viewer-denied"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-006",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 5.0,
            "allocatedQty": 0.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": 5.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.draft.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.get_preorder(preorder_id, meta=Meta(actorId="viewer-1", actorRole="viewer"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Actor is not allowed to read preorder details."
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.get"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_preorder_read"


def test_get_preorder_allows_accountant_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-accountant-read"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-006A",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 7.0,
            "allocatedQty": 1.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": 6.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    detail = preorders.get_preorder(preorder_id, meta=Meta(actorId="acct-1", actorRole="accountant"))

    assert detail.preorderId == preorder_id
    assert detail.remainingQty == 6.0


def test_cancel_preorder_denies_accountant_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-accountant-denied"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-007",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 0.0,
            "deliveredQty": 0.0,
            "cancelledQty": 0.0,
            "remainingQty": 10.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.active.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.cancel_preorder(
            preorder_id,
            CancelPreorderRequest(
                reason="no authority",
                meta=Meta(correlationId="corr-preorder-accountant-cancel", actorId="acct-1", actorRole="accountant"),
            ),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Actor is not allowed to cancel preorders."
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.cancel"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_preorder_write"


def test_completed_preorder_rejects_activate_and_writes_transition_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preorders.postgres_sync, "is_enabled", lambda: False)
    preorder_id = "preorder-completed"
    memory.save_preorder(
        preorder_id,
        {
            "preorderId": preorder_id,
            "tenantId": "default",
            "preorderCode": "DT-005",
            "customerId": "customer-1",
            "productSkuId": "sku-1",
            "committedQty": 10.0,
            "allocatedQty": 0.0,
            "deliveredQty": 10.0,
            "cancelledQty": 0.0,
            "remainingQty": 0.0,
            "deliveryCadence": None,
            "depositAmount": None,
            "notes": None,
            "status": PreorderStatus.completed.value,
            "startDate": None,
            "adjustmentHistory": [],
        },
    )

    with pytest.raises(HTTPException) as exc_info:
        preorders.activate_preorder(
            preorder_id,
            ActivatePreorderRequest(
                meta=Meta(correlationId="corr-preorder-completed-activate", actorId="sales-1", actorRole="sales")
            ),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Preorder transition 'activate' not allowed from state 'completed'."
    assert memory.list_audit_logs()[-1]["reasonCode"] == "state_transition_rejected"
