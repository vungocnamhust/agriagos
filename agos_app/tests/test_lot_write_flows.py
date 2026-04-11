from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models.common import Meta
from app.models.lots import CreateHarvestedLotRequest, ReleaseLotRequest
from app.services import lots
from app.store import memory


def test_create_lot_records_event_audit_and_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    response = lots.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="sku-1",
            sourceType="crop_cycle",
            sourceRefId="cycle-1",
            actualQty=25,
            harvestOrProductionDate="2026-04-11",
            meta=Meta(correlationId="corr-lot", idempotencyKey="idem-lot"),
        )
    )

    assert memory.get_lot(response.data.lotId) is not None
    assert memory.list_events()[-1]["eventName"] == "lot.harvest.created"
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.create"
    assert memory.get_idempotent_result("idem-lot")["data"]["lotId"] == response.data.lotId


def test_release_lot_missing_aggregate_writes_denied_audit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lots.postgres_sync, "is_enabled", lambda: False)

    with pytest.raises(HTTPException) as exc_info:
        lots.release_lot(
            "missing-lot",
            ReleaseLotRequest(releasedQty=5, meta=Meta(correlationId="corr-release")),
        )

    assert exc_info.value.status_code == 404
    assert memory.list_audit_logs()[-1]["actionName"] == "lot.release"
    assert memory.list_audit_logs()[-1]["targetId"] == "missing-lot"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "lot_not_found"
