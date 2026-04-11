from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.preorders import AdjustPreorderRequest, CreatePreorderRequest
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
            meta=Meta(correlationId="corr-preorder", idempotencyKey="idem-preorder"),
        )
    )

    assert memory.get_preorder(response.data.preorderId) is not None
    assert memory.list_events()[-1]["eventName"] == "preorder.placed"
    assert memory.list_audit_logs()[-1]["actionName"] == "preorder.create"
    assert memory.get_idempotent_result("idem-preorder")["data"]["preorderId"] == response.data.preorderId


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
