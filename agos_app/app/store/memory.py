"""
In-memory state store for Phase 1.
Serves as both the event log and read model projections.
Replace with a real DB + event store in Phase 2.
"""
from collections import defaultdict
from datetime import datetime, timezone
import re
from typing import Any
import uuid

# ── Event store (append-only) ─────────────────────────────────────────────────
_event_log: list[dict[str, Any]] = []
_audit_log: list[dict[str, Any]] = []
_inventory_movements: list[dict[str, Any]] = []

# ── Read model projections ────────────────────────────────────────────────────
_customers: dict[str, dict[str, Any]] = {}
_preferences: dict[str, list[dict[str, Any]]] = defaultdict(list)  # customer_id → [pref]
_customer_duplicate_candidates: dict[str, dict[str, Any]] = {}
_organizations: dict[str, dict[str, Any]] = {}
_project_scopes: dict[str, dict[str, Any]] = {}
_project_assignments: dict[str, dict[str, Any]] = {}

_preorders: dict[str, dict[str, Any]] = {}
_orders: dict[str, dict[str, Any]] = {}
_allocations: dict[str, list[dict[str, Any]]] = defaultdict(list)  # order_id → [allocation]

_lots: dict[str, dict[str, Any]] = {}

_plots: dict[str, dict[str, Any]] = {}
_crop_cycles: dict[str, dict[str, Any]] = {}

# ── Idempotency registry ──────────────────────────────────────────────────────
# Maps idempotency_key → stored result payload for deduplication
_idempotency_cache: dict[str, Any] = {}


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("84") and len(digits) > 9:
        return f"0{digits[2:]}"
    return digits


def append_event(event: dict[str, Any]) -> None:
    _event_log.append(event)


def list_events() -> list[dict[str, Any]]:
    return list(_event_log)


def list_customers() -> list[dict[str, Any]]:
    return list(_customers.values())


def list_organizations() -> list[dict[str, Any]]:
    return list(_organizations.values())


def list_project_scopes() -> list[dict[str, Any]]:
    return list(_project_scopes.values())


def list_project_assignments(project_scope_id: str | None = None) -> list[dict[str, Any]]:
    items = list(_project_assignments.values())
    if project_scope_id is not None:
        items = [item for item in items if item.get("projectScopeId") == project_scope_id]
    return items


def list_customer_preferences(customer_id: str) -> list[dict[str, Any]]:
    return list(_preferences.get(customer_id, []))


def list_duplicate_candidates() -> list[dict[str, Any]]:
    return list(_customer_duplicate_candidates.values())


def list_customer_duplicate_candidates(customer_id: str) -> list[dict[str, Any]]:
    return [
        candidate
        for candidate in _customer_duplicate_candidates.values()
        if candidate.get("primaryCustomerId") == customer_id or candidate.get("suspectedCustomerId") == customer_id
    ]


def list_preorders() -> list[dict[str, Any]]:
    return list(_preorders.values())


def list_orders() -> list[dict[str, Any]]:
    return list(_orders.values())


def list_lots() -> list[dict[str, Any]]:
    return list(_lots.values())


def list_plots() -> list[dict[str, Any]]:
    return list(_plots.values())


def list_crop_cycles() -> list[dict[str, Any]]:
    return list(_crop_cycles.values())


def get_customer(customer_id: str) -> dict[str, Any] | None:
    return _customers.get(customer_id)


def get_organization(organization_id: str) -> dict[str, Any] | None:
    return _organizations.get(organization_id)


def get_project_scope(project_scope_id: str) -> dict[str, Any] | None:
    return _project_scopes.get(project_scope_id)


def get_project_assignment(project_assignment_id: str) -> dict[str, Any] | None:
    return _project_assignments.get(project_assignment_id)


def save_customer(customer_id: str, record: dict[str, Any]) -> None:
    _customers[customer_id] = record


def save_organization(organization_id: str, record: dict[str, Any]) -> None:
    _organizations[organization_id] = record


def save_project_scope(project_scope_id: str, record: dict[str, Any]) -> None:
    _project_scopes[project_scope_id] = record


def save_project_assignment(project_assignment_id: str, record: dict[str, Any]) -> None:
    _project_assignments[project_assignment_id] = record


def customer_phone_exists(phone: str) -> bool:
    normalized_phone = _normalize_phone(phone)
    return any(_normalize_phone(customer.get("phone", "")) == normalized_phone for customer in _customers.values())


def get_customer_preferences(customer_id: str) -> list[dict[str, Any]]:
    return list(_preferences[customer_id])


def save_customer_preferences(customer_id: str, preferences: list[dict[str, Any]]) -> None:
    _preferences[customer_id] = list(preferences)


def get_duplicate_candidate(candidate_id: str) -> dict[str, Any] | None:
    return _customer_duplicate_candidates.get(candidate_id)


def save_duplicate_candidate(candidate_id: str, record: dict[str, Any]) -> None:
    _customer_duplicate_candidates[candidate_id] = record


def has_open_duplicate_candidate(primary_customer_id: str, suspected_customer_id: str, match_reason: str) -> bool:
    return any(
        candidate.get("primaryCustomerId") == primary_customer_id
        and candidate.get("suspectedCustomerId") == suspected_customer_id
        and candidate.get("matchReason") == match_reason
        and candidate.get("status") == "open"
        for candidate in _customer_duplicate_candidates.values()
    )


def get_lot(lot_id: str) -> dict[str, Any] | None:
    return _lots.get(lot_id)


def save_lot(lot_id: str, record: dict[str, Any]) -> None:
    _lots[lot_id] = record


def get_or_create_lot(lot_id: str, fallback: dict[str, Any]) -> dict[str, Any]:
    if lot_id not in _lots:
        _lots[lot_id] = dict(fallback)
    return _lots[lot_id]


def get_order(order_id: str) -> dict[str, Any] | None:
    return _orders.get(order_id)


def save_order(order_id: str, record: dict[str, Any]) -> None:
    _orders[order_id] = record


def get_preorder(preorder_id: str) -> dict[str, Any] | None:
    return _preorders.get(preorder_id)


def save_preorder(preorder_id: str, record: dict[str, Any]) -> None:
    _preorders[preorder_id] = record


def has_customer(customer_id: str) -> bool:
    return customer_id in _customers


def get_allocations(order_id: str) -> list[dict[str, Any]]:
    return list(_allocations.get(order_id, []))


def save_allocations(order_id: str, allocations: list[dict[str, Any]]) -> None:
    _allocations[order_id] = list(allocations)


def save_plot(plot_id: str, record: dict[str, Any]) -> None:
    _plots[plot_id] = record


def get_plot(plot_id: str) -> dict[str, Any] | None:
    return _plots.get(plot_id)


def save_crop_cycle(crop_cycle_id: str, record: dict[str, Any]) -> None:
    _crop_cycles[crop_cycle_id] = record


def get_crop_cycle(crop_cycle_id: str) -> dict[str, Any] | None:
    return _crop_cycles.get(crop_cycle_id)


def get_lot_evidence(lot_id: str) -> list[dict[str, Any]]:
    return list(_lots.get(lot_id, {}).get("evidence", []))


def save_lot_evidence(lot_id: str, evidence: list[dict[str, Any]]) -> None:
    lot = get_or_create_lot(lot_id, {"lotId": lot_id})
    lot["evidence"] = list(evidence)


def get_lot_qc_reviews(lot_id: str) -> list[dict[str, Any]]:
    return list(_lots.get(lot_id, {}).get("qcReviews", []))


def save_lot_qc_reviews(lot_id: str, reviews: list[dict[str, Any]]) -> None:
    lot = get_or_create_lot(lot_id, {"lotId": lot_id})
    lot["qcReviews"] = list(reviews)


def now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def query_events(
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    event_name: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
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
    if causation_id:
        result = [e for e in result if e.get("causationId") == causation_id]
    if idempotency_key:
        result = [e for e in result if e.get("idempotencyKey") == idempotency_key]
    return result


def append_audit_log(entry: dict[str, Any]) -> dict[str, Any]:
    audit_entry = {
        "auditId": entry.get("auditId", str(uuid.uuid4())),
        "actorId": entry.get("actorId"),
        "actorRole": entry.get("actorRole"),
        "actionName": entry["actionName"],
        "targetType": entry["targetType"],
        "targetId": entry["targetId"],
        "decision": entry["decision"],
        "reasonCode": entry.get("reasonCode"),
        "beforeSnapshot": entry.get("beforeSnapshot"),
        "afterSnapshot": entry.get("afterSnapshot"),
        "metadata": dict(entry.get("metadata", {})),
        "correlationId": entry.get("correlationId"),
        "createdAt": entry.get("createdAt", now_iso()),
    }
    _audit_log.append(audit_entry)
    return audit_entry


def list_audit_logs() -> list[dict[str, Any]]:
    return list(_audit_log)


def query_audit_logs(
    target_type: str | None = None,
    target_id: str | None = None,
    action_name: str | None = None,
    decision: str | None = None,
    reason_code: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> list[dict[str, Any]]:
    result = list(_audit_log)
    if target_type is not None:
        result = [entry for entry in result if entry.get("targetType") == target_type]
    if target_id is not None:
        result = [entry for entry in result if entry.get("targetId") == target_id]
    if action_name is not None:
        result = [entry for entry in result if entry.get("actionName") == action_name]
    if decision is not None:
        result = [entry for entry in result if entry.get("decision") == decision]
    if reason_code is not None:
        result = [entry for entry in result if entry.get("reasonCode") == reason_code]
    if correlation_id is not None:
        result = [entry for entry in result if entry.get("correlationId") == correlation_id]
    if actor_id is not None:
        result = [entry for entry in result if entry.get("actorId") == actor_id]
    if actor_role is not None:
        result = [entry for entry in result if entry.get("actorRole") == actor_role]
    if created_from is not None:
        created_from_dt = datetime.fromisoformat(created_from)
        result = [
            entry for entry in result if datetime.fromisoformat(entry["createdAt"]) >= created_from_dt
        ]
    if created_to is not None:
        created_to_dt = datetime.fromisoformat(created_to)
        result = [
            entry for entry in result if datetime.fromisoformat(entry["createdAt"]) <= created_to_dt
        ]
    return sorted(
        result,
        key=lambda entry: (entry.get("createdAt") or "", entry.get("auditId") or ""),
        reverse=True,
    )


def append_inventory_movement(entry: dict[str, Any]) -> dict[str, Any]:
    movement = {
        "inventoryMovementId": entry.get("inventoryMovementId", str(uuid.uuid4())),
        "lotId": entry["lotId"],
        "movementType": entry["movementType"],
        "qty": entry["qty"],
        "relatedOrderId": entry.get("relatedOrderId"),
        "relatedOrderLineId": entry.get("relatedOrderLineId"),
        "reason": entry.get("reason"),
        "createdAt": entry.get("createdAt", now_iso()),
    }
    _inventory_movements.append(movement)
    return movement


def list_inventory_movements() -> list[dict[str, Any]]:
    return list(_inventory_movements)


def is_idempotent(key: str) -> bool:
    return key in _idempotency_cache


def get_idempotent_result(key: str) -> Any:
    return _idempotency_cache.get(key)


def set_idempotent_result(key: str, result: Any) -> None:
    _idempotency_cache[key] = result


def reset_state() -> None:
    _event_log.clear()
    _audit_log.clear()
    _inventory_movements.clear()
    _customers.clear()
    _preferences.clear()
    _customer_duplicate_candidates.clear()
    _organizations.clear()
    _project_scopes.clear()
    _project_assignments.clear()
    _preorders.clear()
    _orders.clear()
    _allocations.clear()
    _lots.clear()
    _plots.clear()
    _crop_cycles.clear()
    _idempotency_cache.clear()
