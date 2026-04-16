"""
Domain event factory.
All state changes produce a DomainEvent that is appended to the event store first.

Event naming convention:
  - eventName: dotted lowercase runtime style  e.g. "customer.created", "order.allocated"
  - eventType: PascalCase class style          e.g. "CustomerCreated", "OrderAllocated"

Call emit() with dotted-lowercase event_name. eventType is derived automatically.
Aggregate type labels use short canonical names: Customer, Order, Lot, Preorder, Farm.
"""
import re
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.store import events as store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_event_type(dotted_name: str) -> str:
    """Convert dotted.lowercase event name to PascalCase event type.

    Examples:
        "customer.created"           -> "CustomerCreated"
        "order.cancel_requested"     -> "OrderCancelRequested"
        "lot.harvest.created"        -> "LotHarvestCreated"
    """
    parts = re.split(r"[._]", dotted_name)
    return "".join(p.capitalize() for p in parts if p)


def emit(
    event_name: str | Enum,
    aggregate_type: str | Enum,
    aggregate_id: str,
    payload: dict[str, Any],
    actor_type: str = "user",
    actor_id: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
    event_version: int = 1,
    source: str = "core",
) -> dict[str, Any]:
    """Append a domain event to the event store.

    Args:
        event_name:     Dotted lowercase name, e.g. "order.confirmed".
        aggregate_type: Short canonical label, e.g. "Order", "Lot", "Customer".
        aggregate_id:   UUID of the aggregate root.
        payload:        Minimal stable facts needed by consumers.
        actor_type:     "user" | "system" | "agent" | "integration"
        actor_id:       Identifier of the acting principal (None if system).
        correlation_id: Groups related events across a workflow.
        source:         Event source label, e.g. "core" or "integration".
    """
    normalized_event_name = event_name.value if isinstance(event_name, Enum) else event_name
    normalized_aggregate_type = aggregate_type.value if isinstance(aggregate_type, Enum) else aggregate_type
    event: dict[str, Any] = {
        "eventId": str(uuid.uuid4()),
        "eventName": normalized_event_name,                   # dotted lowercase — runtime/query style
        "eventType": _to_event_type(normalized_event_name),   # PascalCase — class/doc style
        "eventVersion": event_version,
        "aggregateType": normalized_aggregate_type,
        "aggregateId": aggregate_id,
        "occurredAt": _now(),
        "actorType": actor_type,
        "actorId": actor_id,
        "correlationId": correlation_id,
        "causationId": causation_id,
        "idempotencyKey": idempotency_key,
        "source": source,
        "tenantId": "default",
        "payload": payload,
    }
    store.append_event(event)
    return event
