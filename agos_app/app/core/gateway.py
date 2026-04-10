"""
Command Gateway — first checkpoint for every write command.
Responsibilities:
  1. Idempotency deduplication via meta.idempotencyKey
  2. State machine transition enforcement
  3. (Future) RBAC, rate limiting, audit log hook
"""
from typing import Any

from fastapi import HTTPException

from app.store import memory as store

# ── State machines ────────────────────────────────────────────────────────────

# Maps current_state → set of allowed transitions (action name → next_state)
ORDER_TRANSITIONS: dict[str, dict[str, str]] = {
    "pending":   {"confirm": "confirmed", "cancel": "cancelled"},
    "confirmed": {"allocate": "allocated", "cancel": "cancelled"},
    "allocated": {"pack": "packed", "request_cancel": "cancel_requested"},
    "packed":    {"ship": "shipped", "request_cancel": "cancel_requested"},
    "cancel_requested": {"cancel": "cancelled"},
    "shipped":   {"deliver": "delivered"},
    "delivered": {},
    "cancelled": {},
}

LOT_TRANSITIONS: dict[str, dict[str, str]] = {
    "harvested": {"release": "released", "block": "blocked"},
    "released":  {"block": "blocked"},
    "blocked":   {},
}

PREORDER_TRANSITIONS: dict[str, dict[str, str]] = {
    "active":    {"adjust": "active", "cancel": "cancelled"},
    "fulfilled": {},
    "cancelled": {},
}


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
    current = order.get("status", "")
    allowed = ORDER_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Order transition '{action}' not allowed from state '{current}'.",
        )
    return allowed[action]


def assert_lot_transition(lot: dict[str, Any], action: str) -> str:
    current = lot.get("status", "")
    allowed = LOT_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Lot transition '{action}' not allowed from state '{current}'.",
        )
    return allowed[action]


def assert_preorder_transition(preorder: dict[str, Any], action: str) -> str:
    current = preorder.get("status", "")
    allowed = PREORDER_TRANSITIONS.get(current, {})
    if action not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Preorder transition '{action}' not allowed from state '{current}'.",
        )
    return allowed[action]
