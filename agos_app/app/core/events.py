"""
Domain event factory.
All state changes produce a DomainEvent that is appended to the event store first.
"""
import uuid
from datetime import datetime, timezone
from typing import Any

from app.store import memory as store


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    actor_type: str = "user",
    actor_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "eventId": str(uuid.uuid4()),
        "eventName": event_name,
        "aggregateType": aggregate_type,
        "aggregateId": aggregate_id,
        "occurredAt": _now(),
        "actorType": actor_type,
        "actorId": actor_id,
        "correlationId": correlation_id,
        "payload": payload,
    }
    store.append_event(event)
    return event
