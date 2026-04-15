from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.common import Meta
from app.models.preorders import ActivatePreorderRequest, AdjustPreorderRequest, ConfirmPreorderRequest, CreatePreorderRequest
from app.services import preorders as preorder_service
from app.store import _db


@contextmanager
def _bound_read_session(session: Session) -> Iterator[Session]:
    yield session


@contextmanager
def _bound_write_session(session: Session) -> Iterator[tuple[Session, bool]]:
    yield session, False


@contextmanager
def _bound_transaction(session: Session) -> Iterator[Session]:
    yield session


def _bind_postgres_preorder_service(
    monkeypatch: pytest.MonkeyPatch,
    postgres_db_session: Session,
) -> None:
    monkeypatch.setattr(_db, "is_enabled", lambda: True)
    monkeypatch.setattr(_db, "read_session", lambda session=None: _bound_read_session(postgres_db_session))
    monkeypatch.setattr(_db, "write_session", lambda session=None: _bound_write_session(postgres_db_session))
    monkeypatch.setattr(preorder_service.postgres_sync, "is_enabled", lambda: True)
    monkeypatch.setattr(preorder_service, "postgres_transaction", lambda: _bound_transaction(postgres_db_session))


def _seed_customer_and_sku(postgres_db_session: Session) -> tuple[str, str]:
    code_suffix = uuid.uuid4().hex[:8]
    customer_id = str(uuid.uuid4())
    sku_id = str(uuid.uuid4())

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
                status,
                tags,
                notes
            ) VALUES (
                CAST(:customer_id AS uuid),
                :customer_code,
                :full_name,
                :phone,
                :phone_normalized,
                :channel_source,
                :status,
                CAST(:tags AS jsonb),
                :notes
            )
            """
        ),
        {
            "customer_id": customer_id,
            "customer_code": f"KH-PG-{code_suffix}",
            "full_name": "Preorder Integration Customer",
            "phone": f"0901{code_suffix[:6]}",
            "phone_normalized": f"0901{code_suffix[:6]}",
            "channel_source": "zalo",
            "status": "active",
            "tags": '["integration"]',
            "notes": "preorder integration",
        },
    )
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
            "sku_code": f"SKU-PG-{code_suffix}",
            "sku_name": "Preorder Integration Rice",
            "unit": "kg",
            "status": "active",
        },
    )

    return customer_id, sku_id


def _seed_organization(postgres_db_session: Session, organization_id: str) -> None:
    postgres_db_session.execute(
        text(
            """
            INSERT INTO organizations (
                organization_id,
                organization_code,
                name,
                organization_type,
                status
            ) VALUES (
                CAST(:organization_id AS uuid),
                :organization_code,
                :name,
                    'household_producer',
                'active'
            )
            """
        ),
        {
            "organization_id": organization_id,
            "organization_code": f"ORG-{organization_id[-6:].upper()}",
            "name": "Preorder Org",
        },
    )


@pytest.mark.postgres_integration
def test_preorder_core_persists_adjustment_history_and_remaining_qty(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_preorder_service(monkeypatch, postgres_db_session)
    customer_id, sku_id = _seed_customer_and_sku(postgres_db_session)

    created = preorder_service.create_preorder(
        CreatePreorderRequest(
            customerId=customer_id,
            productSkuId=sku_id,
            committedQty=20,
            meta=Meta(
                correlationId="corr-pg-preorder-create",
                idempotencyKey="idem-pg-preorder-create",
                actorId="sales-1",
                actorRole="sales",
            ),
        )
    )
    preorder_service.confirm_preorder(
        created.data.preorderId,
        ConfirmPreorderRequest(
            meta=Meta(
                correlationId="corr-pg-preorder-confirm",
                idempotencyKey="idem-pg-preorder-confirm",
                actorId="sales-1",
                actorRole="sales",
            )
        ),
    )
    preorder_service.activate_preorder(
        created.data.preorderId,
        ActivatePreorderRequest(
            meta=Meta(
                correlationId="corr-pg-preorder-activate",
                idempotencyKey="idem-pg-preorder-activate",
                actorId="sales-1",
                actorRole="sales",
            )
        ),
    )

    # Manual SQL simulates downstream allocation and delivery totals on the same preorder.
    postgres_db_session.execute(
        text(
            """
            UPDATE preorders
            SET allocated_qty = 4,
                delivered_qty = 3,
                remaining_qty = 13,
                updated_at = now()
            WHERE preorder_id = CAST(:preorder_id AS uuid)
            """
        ),
        {"preorder_id": created.data.preorderId},
    )
    intermediate = preorder_service.get_preorder(
        created.data.preorderId,
        meta=Meta(actorId="sales-1", actorRole="sales"),
    )

    assert intermediate.allocatedQty == 4
    assert intermediate.deliveredQty == 3
    assert intermediate.remainingQty == 13

    adjusted = preorder_service.adjust_preorder(
        created.data.preorderId,
        AdjustPreorderRequest(
            newCommittedQty=25,
            reason="expand commitment",
            meta=Meta(
                correlationId="corr-pg-preorder-adjust",
                idempotencyKey="idem-pg-preorder-adjust",
                actorId="sales-2",
                actorRole="sales",
            ),
        ),
    )
    detail = preorder_service.get_preorder(
        created.data.preorderId,
        meta=Meta(actorId="sales-2", actorRole="sales"),
    )

    assert adjusted.data.status == "active"
    assert adjusted.data.remainingQty == 18
    assert detail.remainingQty == 18
    assert len(detail.adjustmentHistory) == 1
    assert detail.adjustmentHistory[0].oldCommittedQty == 20
    assert detail.adjustmentHistory[0].newCommittedQty == 25
    assert detail.adjustmentHistory[0].reason == "expand commitment"
    assert detail.adjustmentHistory[0].actorId == "sales-2"

    persisted = postgres_db_session.execute(
        text(
            """
            SELECT committed_qty, allocated_qty, delivered_qty, cancelled_qty, remaining_qty, status
            FROM preorders
            WHERE preorder_id = CAST(:preorder_id AS uuid)
            """
        ),
        {"preorder_id": created.data.preorderId},
    ).mappings().first()
    adjustment_rows = postgres_db_session.execute(
        text(
            """
            SELECT old_committed_qty, new_committed_qty, reason, actor_id
            FROM preorder_adjustments
            WHERE preorder_id = CAST(:preorder_id AS uuid)
            ORDER BY changed_at DESC, adjustment_id DESC
            """
        ),
        {"preorder_id": created.data.preorderId},
    ).mappings().all()

    assert persisted is not None
    assert float(persisted["committed_qty"]) == 25
    assert float(persisted["allocated_qty"]) == 4
    assert float(persisted["delivered_qty"]) == 3
    assert float(persisted["cancelled_qty"]) == 0
    assert float(persisted["remaining_qty"]) == 18
    assert persisted["status"] == "active"
    assert len(adjustment_rows) == 1
    assert float(adjustment_rows[0]["old_committed_qty"]) == 20
    assert float(adjustment_rows[0]["new_committed_qty"]) == 25
    assert adjustment_rows[0]["reason"] == "expand commitment"
    assert adjustment_rows[0]["actor_id"] == "sales-2"


@pytest.mark.postgres_integration
def test_create_preorder_persists_organization_id_on_postgres_path(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_preorder_service(monkeypatch, postgres_db_session)
    customer_id, sku_id = _seed_customer_and_sku(postgres_db_session)
    organization_id = str(uuid.uuid4())
    _seed_organization(postgres_db_session, organization_id)

    created = preorder_service.create_preorder(
        CreatePreorderRequest(
            customerId=customer_id,
            productSkuId=sku_id,
            committedQty=20,
            organizationId=organization_id,
            meta=Meta(
                correlationId="corr-pg-preorder-org-create",
                idempotencyKey="idem-pg-preorder-org-create",
                actorId="sales-1",
                actorRole="sales",
            ),
        )
    )

    row = postgres_db_session.execute(
        text("SELECT organization_id::text FROM preorders WHERE preorder_id = CAST(:preorder_id AS uuid)"),
        {"preorder_id": created.data.preorderId},
    ).mappings().one()

    assert row["organization_id"] == organization_id
    assert created.data.organizationId == organization_id


@pytest.mark.postgres_integration
def test_preorder_adjust_rejects_below_allocated_and_delivered_floor_on_postgres(
    postgres_db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bind_postgres_preorder_service(monkeypatch, postgres_db_session)
    customer_id, sku_id = _seed_customer_and_sku(postgres_db_session)

    created = preorder_service.create_preorder(
        CreatePreorderRequest(
            customerId=customer_id,
            productSkuId=sku_id,
            committedQty=12,
            meta=Meta(
                correlationId="corr-pg-preorder-create-floor",
                idempotencyKey="idem-pg-preorder-create-floor",
                actorId="sales-1",
                actorRole="sales",
            ),
        )
    )
    preorder_service.confirm_preorder(
        created.data.preorderId,
        ConfirmPreorderRequest(
            meta=Meta(
                correlationId="corr-pg-preorder-confirm-floor",
                idempotencyKey="idem-pg-preorder-confirm-floor",
                actorId="sales-1",
                actorRole="sales",
            )
        ),
    )
    preorder_service.activate_preorder(
        created.data.preorderId,
        ActivatePreorderRequest(
            meta=Meta(
                correlationId="corr-pg-preorder-activate-floor",
                idempotencyKey="idem-pg-preorder-activate-floor",
                actorId="sales-1",
                actorRole="sales",
            )
        ),
    )

    postgres_db_session.execute(
        text(
            """
            UPDATE preorders
            SET allocated_qty = 4,
                delivered_qty = 3,
                remaining_qty = 5,
                updated_at = now()
            WHERE preorder_id = CAST(:preorder_id AS uuid)
            """
        ),
        {"preorder_id": created.data.preorderId},
    )

    with pytest.raises(HTTPException) as exc_info:
        preorder_service.adjust_preorder(
            created.data.preorderId,
            AdjustPreorderRequest(
                newCommittedQty=6,
                reason="invalid shrink",
                meta=Meta(
                    correlationId="corr-pg-preorder-adjust-floor",
                    idempotencyKey="idem-pg-preorder-adjust-floor",
                    actorId="sales-2",
                    actorRole="sales",
                ),
            ),
        )

    error = exc_info.value
    assert error.status_code == 422
    assert "allocated + delivered qty (7.0)" in str(error.detail)