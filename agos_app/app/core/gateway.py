"""
Command Gateway — first checkpoint for every write command.
Responsibilities:
  1. Idempotency deduplication via meta.idempotencyKey
  2. State machine transition enforcement
  3. (Future) RBAC, rate limiting, audit log hook
"""
from typing import Any

from fastapi import HTTPException

from app.models.enums import LotStatus, OrderStatus, OrganizationStatus, PreorderStatus
from app.store import idempotency as idempotency_store
from app.store import memory as store
from app.store._db import is_enabled as postgres_enabled

# ── State machines ────────────────────────────────────────────────────────────

# Maps current_state → allowed transitions (action name → allowed next states)
ORDER_TRANSITIONS: dict[str, dict[str, tuple[str, ...]]] = {
    OrderStatus.draft.value: {
        "confirm": (OrderStatus.confirmed.value,),
        "cancel": (OrderStatus.cancelled.value,),
    },
    OrderStatus.confirmed.value: {
        "allocate": (OrderStatus.allocated.value, OrderStatus.partially_allocated.value),
        "cancel": (OrderStatus.cancelled.value,),
    },
    OrderStatus.partially_allocated.value: {
        "allocate": (OrderStatus.allocated.value,),
        "pack": (OrderStatus.partially_packed.value,),
        "request_cancel": (OrderStatus.cancel_requested.value,),
    },
    OrderStatus.allocated.value: {
        "pack": (OrderStatus.packed.value, OrderStatus.partially_packed.value),
        "request_cancel": (OrderStatus.cancel_requested.value,),
    },
    OrderStatus.partially_packed.value: {
        "pack": (OrderStatus.packed.value,),
    },
    OrderStatus.packed.value: {
        "ship": (OrderStatus.shipped.value,),
        "request_cancel": (OrderStatus.cancel_requested.value,),
    },
    OrderStatus.cancel_requested.value: {"cancel": (OrderStatus.cancelled.value,)},
    OrderStatus.shipped.value: {
        "deliver": (OrderStatus.delivered.value, OrderStatus.partially_delivered.value),
        "fail_delivery": (OrderStatus.failed.value,),
    },
    OrderStatus.partially_delivered.value: {
        "deliver": (OrderStatus.delivered.value,),
        "fail_delivery": (OrderStatus.failed.value,),
    },
    OrderStatus.delivered.value: {},
    OrderStatus.failed.value: {},
    OrderStatus.cancelled.value: {},
}

LOT_TRANSITIONS: dict[str, dict[str, str]] = {
    # Phase 1: lots are initialized in harvested or qc_pending by the service layer.
    LotStatus.harvested.value: {"release": LotStatus.released.value, "block": LotStatus.blocked.value},
    LotStatus.qc_pending.value: {"release": LotStatus.released.value, "block": LotStatus.blocked.value},
    LotStatus.released.value: {"block": LotStatus.blocked.value},
    LotStatus.blocked.value: {"unblock": LotStatus.qc_pending.value},
    # Phase 2 states — not reachable via gateway in Phase 1:
    # LotStatus.draft.value: {"harvest": LotStatus.harvested.value}
    # LotStatus.qc_pending.value: transitions handled by QC workflow module
    # LotStatus.depleted.value: {}  — terminal, set by allocation consumption
    # LotStatus.closed.value: {}    — terminal, set by admin
}

PREORDER_TRANSITIONS: dict[str, dict[str, str]] = {
    PreorderStatus.draft.value: {
        "confirm": PreorderStatus.confirmed.value,
        "cancel": PreorderStatus.cancelled.value,
    },
    PreorderStatus.confirmed.value: {
        "activate": PreorderStatus.active.value,
        "adjust": PreorderStatus.confirmed.value,
        "cancel": PreorderStatus.cancelled.value,
    },
    PreorderStatus.active.value: {
        "adjust": PreorderStatus.active.value,
        "cancel": PreorderStatus.cancelled.value,
    },
    PreorderStatus.completed.value: {},
    PreorderStatus.cancelled.value: {},
}

ORGANIZATION_TRANSITIONS: dict[str, dict[str, str]] = {
    OrganizationStatus.draft.value: {
        "activate": OrganizationStatus.active.value,
        "close": OrganizationStatus.closed.value,
    },
    OrganizationStatus.active.value: {
        "pause": OrganizationStatus.paused.value,
    },
    OrganizationStatus.paused.value: {
        "activate": OrganizationStatus.active.value,
        "close": OrganizationStatus.closed.value,
    },
    OrganizationStatus.closed.value: {},
}

LEGACY_ORDER_STATES: dict[str, str] = {
    "pending": OrderStatus.draft.value,
}

LEGACY_PREORDER_STATES: dict[str, str] = {
    "fulfilled": PreorderStatus.completed.value,
}


def _normalize_legacy_order_state(current: str) -> str:
    return LEGACY_ORDER_STATES.get(current, current)


def _normalize_legacy_preorder_state(current: str) -> str:
    return LEGACY_PREORDER_STATES.get(current, current)


def check_idempotency(idempotency_key: str | None) -> Any | None:
    """Return cached result if this key was already processed, else None."""
    if not idempotency_key:
        return None

    if postgres_enabled():
        return idempotency_store.fetch_response(idempotency_key)

    if store.is_idempotent(idempotency_key):
        return store.get_idempotent_result(idempotency_key)
    return None


def record_idempotency(
    idempotency_key: str | None,
    result: Any,
    *,
    operation_name: str = "core.write",
    request_hash: str | None = None,
) -> None:
    if idempotency_key:
        if postgres_enabled():
            idempotency_store.save_response(
                idempotency_key,
                result,
                operation_name=operation_name,
                request_hash=request_hash,
            )
        store.set_idempotent_result(idempotency_key, result)


def assert_order_transition(order: dict[str, Any], action: str) -> str:
    """Return the next state or raise 422 if the transition is not allowed."""
    original = order.get("status", "")
    current = _normalize_legacy_order_state(original)
    allowed = ORDER_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Order transition '{action}' not allowed from state '{original}'.",
        )
    return allowed[action][0]


def assert_order_transition_outcome(order: dict[str, Any], action: str, next_state: str) -> str:
    """Return the validated next state or raise 422 if the target outcome is not allowed."""
    original = order.get("status", "")
    current = _normalize_legacy_order_state(original)
    allowed = ORDER_TRANSITIONS.get(current, {})
    allowed_targets = allowed.get(action)
    if allowed_targets is None or next_state not in allowed_targets:
        raise HTTPException(
            status_code=422,
            detail=f"Order transition '{action}' not allowed from state '{original}'.",
        )
    return next_state


def assert_lot_transition(lot: dict[str, Any], action: str) -> str:
    # Lot states were introduced after enum standardization, so there is no
    # legacy alias mapping to normalize here.
    current = lot.get("status", "")
    allowed = LOT_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Lot transition '{action}' not allowed from state '{current}'.",
        )
    return allowed[action]


def assert_preorder_transition(preorder: dict[str, Any], action: str) -> str:
    original = preorder.get("status", "")
    current = _normalize_legacy_preorder_state(original)
    allowed = PREORDER_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Preorder transition '{action}' not allowed from state '{original}'.",
        )
    return allowed[action]


def assert_organization_transition(organization: dict[str, Any], action: str) -> str:
    current = organization.get("status", "")
    allowed = ORGANIZATION_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Organization transition '{action}' not allowed from state '{current}'.",
        )
    return allowed[action]
