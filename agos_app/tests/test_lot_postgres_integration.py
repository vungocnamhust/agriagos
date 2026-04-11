# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.lots import (
    BlockLotRequest,
    CreateHarvestedLotRequest,
    CreateProcessedLotRequest,
    CreateQCReviewRequest,
    ReleaseLotRequest,
    UnblockLotRequest,
)
from app.services import lots as lot_service
from app.store import _db
from app.store import farm as farm_store
from app.store import lots as lot_store


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
def test_harvested_lot_persists_unit_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(lot_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(lot_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))
    monkeypatch.setattr(farm_store, "is_enabled", lambda: True)

    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-LOT-1', 'Lot SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000111"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (plot_id, tenant_id, plot_code, name, area_value, area_unit, status)
            VALUES (:plot_id, 'default', 'PLOT-1', 'Plot 1', 10, 'ha', 'active')
            """
        ),
        {"plot_id": "00000000-0000-0000-0000-000000000211"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO crop_cycles (
                crop_cycle_id,
                tenant_id,
                plot_id,
                crop_name,
                start_date,
                growth_stage,
                status
            ) VALUES (
                :crop_cycle_id,
                'default',
                :plot_id,
                'rice',
                DATE '2026-03-01',
                'harvested',
                'harvested'
            )
            """
        ),
        {
            "crop_cycle_id": "00000000-0000-0000-0000-000000000311",
            "plot_id": "00000000-0000-0000-0000-000000000211",
        },
    )

    created = lot_service.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="00000000-0000-0000-0000-000000000111",
            sourceType="crop_cycle",
            sourceRefId="00000000-0000-0000-0000-000000000311",
            actualQty=25,
            unit="KG",
            harvestOrProductionDate="2026-04-11T00:00:00+00:00",
            meta=Meta(correlationId="corr-lot-pg-create", idempotencyKey="idem-lot-pg-create"),
        )
    )

    stored = lot_store.fetch_lot(created.data.lotId)

    assert stored is not None
    assert stored["unit"] == "kg"
    assert stored["status"] == "harvested"
    assert stored["sourceRefId"] == "00000000-0000-0000-0000-000000000311"


@pytest.mark.postgres_integration
def test_processed_lot_persists_processing_batch_source_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(lot_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(lot_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))
    monkeypatch.setattr(farm_store, "is_enabled", lambda: True)

    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-LOT-2', 'Processed Lot SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000112"},
    )

    created = lot_service.create_processed_lot(
        CreateProcessedLotRequest(
            productSkuId="00000000-0000-0000-0000-000000000112",
            processRefId="PROC-2026-0001",
            actualQty=12,
            unit="KG",
            harvestOrProductionDate="2026-04-12T00:00:00+00:00",
            meta=Meta(correlationId="corr-lot-pg-processed", idempotencyKey="idem-lot-pg-processed"),
        )
    )

    stored = lot_store.fetch_lot(created.data.lotId)

    assert stored is not None
    assert stored["unit"] == "kg"
    assert stored["status"] == "harvested"
    assert stored["sourceType"] == "processing_batch"
    assert stored["sourceRefId"] == "PROC-2026-0001"


@pytest.mark.postgres_integration
def test_lot_release_block_unblock_persists_quantity_snapshots_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(lot_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(lot_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))
    monkeypatch.setattr(farm_store, "is_enabled", lambda: True)

    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-LOT-3', 'Lot Snapshot SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000113"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO plots (plot_id, tenant_id, plot_code, name, area_value, area_unit, status)
            VALUES (:plot_id, 'default', 'PLOT-3', 'Plot 3', 10, 'ha', 'active')
            """
        ),
        {"plot_id": "00000000-0000-0000-0000-000000000213"},
    )
    postgres_db_session.execute(
        text(
            """
            INSERT INTO crop_cycles (
                crop_cycle_id,
                tenant_id,
                plot_id,
                crop_name,
                start_date,
                growth_stage,
                status
            ) VALUES (
                :crop_cycle_id,
                'default',
                :plot_id,
                'rice',
                DATE '2026-03-01',
                'harvested',
                'harvested'
            )
            """
        ),
        {
            "crop_cycle_id": "00000000-0000-0000-0000-000000000313",
            "plot_id": "00000000-0000-0000-0000-000000000213",
        },
    )

    created = lot_service.create_harvested_lot(
        CreateHarvestedLotRequest(
            productSkuId="00000000-0000-0000-0000-000000000113",
            sourceType="crop_cycle",
            sourceRefId="00000000-0000-0000-0000-000000000313",
            actualQty=25,
            unit="KG",
            harvestOrProductionDate="2026-04-11T00:00:00+00:00",
            requiresQc=True,
            meta=Meta(correlationId="corr-lot-pg-snapshots-create", idempotencyKey="idem-lot-pg-snapshots-create"),
        )
    )

    lot_service.create_lot_qc_review(
        created.data.lotId,
        CreateQCReviewRequest(
            checklistVersion="v1",
            result="passed",
            meta=Meta(correlationId="corr-lot-pg-snapshots-qc", idempotencyKey="idem-lot-pg-snapshots-qc"),
        ),
    )

    released = lot_service.release_lot(
        created.data.lotId,
        ReleaseLotRequest(
            releasedQty=10,
            meta=Meta(correlationId="corr-lot-pg-snapshots-release", idempotencyKey="idem-lot-pg-snapshots-release"),
        ),
    )

    released_row = lot_store.fetch_lot(created.data.lotId)
    assert released.data.status == "released"
    assert released_row is not None
    assert released_row["releasedQty"] == 10
    assert released_row["availableQty"] == 10
    assert released_row["reservedQty"] == 0

    blocked = lot_service.block_lot(
        created.data.lotId,
        BlockLotRequest(
            reason="hold for review",
            meta=Meta(correlationId="corr-lot-pg-snapshots-block", idempotencyKey="idem-lot-pg-snapshots-block"),
        ),
    )

    blocked_row = lot_store.fetch_lot(created.data.lotId)
    assert blocked.data.status == "blocked"
    assert blocked_row is not None
    assert blocked_row["releasedQty"] == 0
    assert blocked_row["availableQty"] == 0
    assert blocked_row["reservedQty"] == 0

    unblocked = lot_service.unblock_lot(
        created.data.lotId,
        UnblockLotRequest(
            reason="review restarted",
            meta=Meta(correlationId="corr-lot-pg-snapshots-unblock", idempotencyKey="idem-lot-pg-snapshots-unblock"),
        ),
    )

    unblocked_row = lot_store.fetch_lot(created.data.lotId)
    assert unblocked.data.status == "qc_pending"
    assert unblocked_row is not None
    assert unblocked_row["releasedQty"] == 0
    assert unblocked_row["availableQty"] == 0
    assert unblocked_row["reservedQty"] == 0

    event_rows = postgres_db_session.execute(
        text(
            """
            SELECT event_name, payload
            FROM domain_events
            WHERE aggregate_id = :lot_id
              AND event_name IN ('lot.released', 'lot.blocked', 'lot.unblocked')
            ORDER BY occurred_at ASC, event_id ASC
            """
        ),
        {"lot_id": created.data.lotId},
    ).mappings().all()

    assert [row["event_name"] for row in event_rows] == ["lot.released", "lot.blocked", "lot.unblocked"]
    assert event_rows[0]["payload"]["releasedQty"] == 10
    assert event_rows[0]["payload"]["availableQty"] == 10
    assert event_rows[1]["payload"]["releasedQty"] == 0
    assert event_rows[1]["payload"]["availableQty"] == 0
    assert event_rows[2]["payload"]["releasedQty"] == 0
    assert event_rows[2]["payload"]["availableQty"] == 0


@pytest.mark.postgres_integration
def test_atomic_lot_helpers_update_quantity_snapshots(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))

    postgres_db_session.execute(
        text(
            """
            INSERT INTO product_skus (product_sku_id, tenant_id, sku_code, sku_name, unit, status)
            VALUES (:product_sku_id, 'default', 'SKU-LOT-4', 'Atomic Lot SKU', 'kg', 'active')
            """
        ),
        {"product_sku_id": "00000000-0000-0000-0000-000000000113"},
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
                unit,
                quality_note,
                status
            ) VALUES (
                :lot_id,
                'default',
                'LOT-ATOMIC-1',
                :product_sku_id,
                'crop_cycle',
                'cycle-atomic',
                TIMESTAMPTZ '2026-04-11T00:00:00+00:00',
                25,
                0,
                0,
                0,
                'kg',
                NULL,
                'harvested'
            )
            """
        ),
        {
            "lot_id": "00000000-0000-0000-0000-000000000413",
            "product_sku_id": "00000000-0000-0000-0000-000000000113",
        },
    )

    released = lot_store.release_lot_atomic("00000000-0000-0000-0000-000000000413", next_status="released", released_qty=12)
    assert released is not None
    assert released["status"] == "released"
    assert released["releasedQty"] == 12
    assert released["availableQty"] == 12

    blocked = lot_store.block_lot_atomic("00000000-0000-0000-0000-000000000413", next_status="blocked")
    assert blocked is not None
    assert blocked["status"] == "blocked"
    assert blocked["releasedQty"] == 0
    assert blocked["availableQty"] == 0

    unblocked = lot_store.unblock_lot_atomic("00000000-0000-0000-0000-000000000413", next_status="qc_pending")
    assert unblocked is not None
    assert unblocked["status"] == "qc_pending"
    assert unblocked["releasedQty"] == 0
    assert unblocked["availableQty"] == 0