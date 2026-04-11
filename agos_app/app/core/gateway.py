"""
Command Gateway — first checkpoint for every write command.
Responsibilities:
  1. Idempotency deduplication via meta.idempotencyKey
  2. State machine transition enforcement
  3. (Future) RBAC, rate limiting, audit log hook
"""
from typing import Any

from fastapi import HTTPException

from app.models.enums import LotStatus, OrderStatus, PreorderStatus
from app.store import memory as store

# ── State machines ────────────────────────────────────────────────────────────

# Maps current_state → set of allowed transitions (action name → next_state)
ORDER_TRANSITIONS: dict[str, dict[str, str]] = {
    OrderStatus.draft.value: {"confirm": OrderStatus.confirmed.value, "cancel": OrderStatus.cancelled.value},
    OrderStatus.confirmed.value: {"allocate": OrderStatus.allocated.value, "cancel": OrderStatus.cancelled.value},
    OrderStatus.allocated.value: {"pack": OrderStatus.packed.value, "request_cancel": OrderStatus.cancel_requested.value},
    OrderStatus.packed.value: {"ship": OrderStatus.shipped.value, "request_cancel": OrderStatus.cancel_requested.value},
    OrderStatus.cancel_requested.value: {"cancel": OrderStatus.cancelled.value},
    OrderStatus.shipped.value: {"deliver": OrderStatus.delivered.value},
    OrderStatus.delivered.value: {},
    OrderStatus.cancelled.value: {},
}

LOT_TRANSITIONS: dict[str, dict[str, str]] = {
    # Phase 1: lots are created directly in "harvested" state by the service layer.
    # "draft" state exists in LotStatus enum but is not used until Phase 2 (lot creation workflow).
    LotStatus.harvested.value: {"release": LotStatus.released.value, "block": LotStatus.blocked.value},
    LotStatus.released.value: {"block": LotStatus.blocked.value},
    LotStatus.blocked.value: {},
    # Phase 2 states — not reachable via gateway in Phase 1:
    # LotStatus.draft.value: {"harvest": LotStatus.harvested.value}
    # LotStatus.qc_pending.value: transitions handled by QC workflow module
    # LotStatus.depleted.value: {}  — terminal, set by allocation consumption
    # LotStatus.closed.value: {}    — terminal, set by admin
}

PREORDER_TRANSITIONS: dict[str, dict[str, str]] = {
    # Phase 1: preorders are created directly in "active" state.
    # "draft" and "confirmed" states exist in PreorderStatus enum but the
    # full draft→confirmed→active lifecycle is deferred to Phase 1.5.
    PreorderStatus.active.value: {"adjust": PreorderStatus.active.value, "cancel": PreorderStatus.cancelled.value},
    PreorderStatus.completed.value: {},
    PreorderStatus.cancelled.value: {},
    # Phase 1.5 states — not reachable via gateway in Phase 1:
    # PreorderStatus.draft.value: {"confirm": PreorderStatus.confirmed.value, "cancel": PreorderStatus.cancelled.value}
    # PreorderStatus.confirmed.value: {"activate": PreorderStatus.active.value, "cancel": PreorderStatus.cancelled.value}
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
    if idempotency_key and store.is_idempotent(idempotency_key):
        return store.get_idempotent_result(idempotency_key)
    return None


def record_idempotency(idempotency_key: str | None, result: Any) -> None:
    if idempotency_key:
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
    return allowed[action]


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
