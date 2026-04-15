from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.gateway import (
    assert_lot_transition,
    assert_organization_transition,
    assert_order_transition_outcome,
    assert_preorder_transition,
)
from app.models.enums import LotStatus, OrderStatus, OrganizationStatus, PreorderStatus


def test_order_transition_outcome_allows_partial_allocate_from_confirmed() -> None:
    next_status = assert_order_transition_outcome(
        {"status": OrderStatus.confirmed.value},
        "allocate",
        OrderStatus.partially_allocated.value,
    )

    assert next_status == OrderStatus.partially_allocated.value


def test_order_transition_outcome_allows_partial_pack_from_allocated() -> None:
    next_status = assert_order_transition_outcome(
        {"status": OrderStatus.allocated.value},
        "pack",
        OrderStatus.partially_packed.value,
    )

    assert next_status == OrderStatus.partially_packed.value


def test_order_transition_outcome_rejects_invalid_target_status() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_order_transition_outcome(
            {"status": OrderStatus.confirmed.value},
            "allocate",
            OrderStatus.shipped.value,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Order transition 'allocate' not allowed from state 'confirmed'."


def test_preorder_completed_is_terminal() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_preorder_transition({"status": PreorderStatus.completed.value}, "activate")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Preorder transition 'activate' not allowed from state 'completed'."


def test_lot_blocked_can_only_move_to_qc_pending() -> None:
    next_status = assert_lot_transition({"status": LotStatus.blocked.value}, "unblock")

    assert next_status == LotStatus.qc_pending.value


def test_lot_blocked_cannot_move_directly_to_released() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_lot_transition({"status": LotStatus.blocked.value}, "release")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Lot transition 'release' not allowed from state 'blocked'."


def test_organization_draft_can_activate() -> None:
    next_status = assert_organization_transition(
        {"status": OrganizationStatus.draft.value},
        "activate",
    )

    assert next_status == OrganizationStatus.active.value


def test_organization_draft_can_close() -> None:
    next_status = assert_organization_transition(
        {"status": OrganizationStatus.draft.value},
        "close",
    )

    assert next_status == OrganizationStatus.closed.value


def test_organization_active_can_pause() -> None:
    next_status = assert_organization_transition(
        {"status": OrganizationStatus.active.value},
        "pause",
    )

    assert next_status == OrganizationStatus.paused.value


def test_organization_paused_can_close() -> None:
    next_status = assert_organization_transition(
        {"status": OrganizationStatus.paused.value},
        "close",
    )

    assert next_status == OrganizationStatus.closed.value


def test_organization_paused_can_reactivate() -> None:
    next_status = assert_organization_transition(
        {"status": OrganizationStatus.paused.value},
        "activate",
    )

    assert next_status == OrganizationStatus.active.value


def test_organization_closed_is_terminal() -> None:
    with pytest.raises(HTTPException) as exc_info:
        assert_organization_transition({"status": OrganizationStatus.closed.value}, "activate")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Organization transition 'activate' not allowed from state 'closed'."