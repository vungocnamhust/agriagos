"""
In-memory state store for Phase 1.
Serves as both the event log and read model projections.
Replace with a real DB + event store in Phase 2.
"""
from collections import defaultdict
from typing import Any

# ── Event store (append-only) ─────────────────────────────────────────────────
_event_log: list[dict[str, Any]] = []

# ── Read model projections ────────────────────────────────────────────────────
_customers: dict[str, dict[str, Any]] = {}
_preferences: dict[str, list[dict[str, Any]]] = defaultdict(list)  # customer_id → [pref]

_preorders: dict[str, dict[str, Any]] = {}
_orders: dict[str, dict[str, Any]] = {}
_allocations: dict[str, list[dict[str, Any]]] = defaultdict(list)  # order_id → [allocation]

_lots: dict[str, dict[str, Any]] = {}

_plots: dict[str, dict[str, Any]] = {}
_crop_cycles: dict[str, dict[str, Any]] = {}

# ── Idempotency registry ──────────────────────────────────────────────────────
# Maps idempotency_key → stored result payload for deduplication
_idempotency_cache: dict[str, Any] = {}


def append_event(event: dict[str, Any]) -> None:
    _event_log.append(event)


def query_events(
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    event_name: str | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    result = _event_log
    if aggregate_type:
        result = [e for e in result if e.get("aggregateType") == aggregate_type]
    if aggregate_id:
        result = [e for e in result if e.get("aggregateId") == aggregate_id]
    if event_name:
        result = [e for e in result if e.get("eventName") == event_name]
    if correlation_id:
        result = [e for e in result if e.get("correlationId") == correlation_id]
    return result


def is_idempotent(key: str) -> bool:
    return key in _idempotency_cache


def get_idempotent_result(key: str) -> Any:
    return _idempotency_cache.get(key)


def set_idempotent_result(key: str, result: Any) -> None:
    _idempotency_cache[key] = result
