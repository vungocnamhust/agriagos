# pyright: reportMissingImports=false
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.lots import CreateHarvestedLotRequest, CreateProcessedLotRequest
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