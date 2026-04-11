"""Domain event store operations."""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from app.store import _db
from app.store import memory

__all__ = ["append_event", "query_events"]


def _to_event_type(dotted_name: str) -> str:
    parts = re.split(r"[._]", dotted_name)
    return "".join(part.capitalize() for part in parts if part)


def append_event(event: dict[str, Any]) -> None:
    if not _db.is_enabled():
        memory.append_event(event)
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO domain_events (
                    event_id,
                    tenant_id,
                    event_name,
                    event_version,
                    aggregate_type,
                    aggregate_id,
                    occurred_at,
                    actor_type,
                    actor_id,
                    correlation_id,
                    causation_id,
                    idempotency_key,
                    source,
                    payload
                ) VALUES (
                    :event_id,
                    :tenant_id,
                    :event_name,
                    :event_version,
                    :aggregate_type,
                    :aggregate_id,
                    CAST(:occurred_at AS timestamptz),
                    :actor_type,
                    :actor_id,
                    :correlation_id,
                    :causation_id,
                    :idempotency_key,
                    :source,
                    CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "event_id": event["eventId"],
                "tenant_id": event.get("tenantId", "default"),
                "event_name": event["eventName"],
                "event_version": event.get("eventVersion", 1),
                "aggregate_type": event["aggregateType"],
                "aggregate_id": event["aggregateId"],
                "occurred_at": event["occurredAt"],
                "actor_type": event["actorType"],
                "actor_id": event.get("actorId"),
                "correlation_id": event.get("correlationId"),
                "causation_id": event.get("causationId"),
                "idempotency_key": event.get("idempotencyKey"),
                "source": event.get("source", "core"),
                "payload": json.dumps(event.get("payload", {})),
            },
        )
        if should_commit:
            session.commit()


def query_events(
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    event_name: str | None = None,
    correlation_id: str | None = None,
    causation_id: str | None = None,
    idempotency_key: str | None = None,
) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return memory.query_events(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_name=event_name,
            correlation_id=correlation_id,
            causation_id=causation_id,
            idempotency_key=idempotency_key,
        )

    where_clauses: list[str] = []
    params: dict[str, Any] = {}
    if aggregate_type is not None:
        where_clauses.append("aggregate_type = :aggregate_type")
        params["aggregate_type"] = aggregate_type
    if aggregate_id is not None:
        where_clauses.append("aggregate_id = :aggregate_id")
        params["aggregate_id"] = aggregate_id
    if event_name is not None:
        where_clauses.append("event_name = :event_name")
        params["event_name"] = event_name
    if correlation_id is not None:
        where_clauses.append("correlation_id = :correlation_id")
        params["correlation_id"] = correlation_id
    if causation_id is not None:
        where_clauses.append("causation_id = :causation_id")
        params["causation_id"] = causation_id
    if idempotency_key is not None:
        where_clauses.append("idempotency_key = :idempotency_key")
        params["idempotency_key"] = idempotency_key

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with _db.read_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT
                    event_id,
                    tenant_id,
                    event_name,
                    event_version,
                    aggregate_type,
                    aggregate_id,
                    occurred_at,
                    actor_type,
                    actor_id,
                    correlation_id,
                    causation_id,
                    idempotency_key,
                    source,
                    payload
                FROM domain_events
                {where_sql}
                ORDER BY occurred_at DESC, event_id DESC
                """
            ),
            params,
        ).mappings().all()

    return [
        {
            "eventId": str(row["event_id"]),
            "tenantId": row["tenant_id"],
            "eventName": row["event_name"],
            "eventType": _to_event_type(row["event_name"]),
            "eventVersion": row["event_version"],
            "aggregateType": row["aggregate_type"],
            "aggregateId": row["aggregate_id"],
            "occurredAt": row["occurred_at"].isoformat() if row["occurred_at"] else None,
            "actorType": row["actor_type"],
            "actorId": row["actor_id"],
            "correlationId": row["correlation_id"],
            "causationId": row["causation_id"],
            "idempotencyKey": row["idempotency_key"],
            "source": row["source"],
            "payload": row["payload"],
        }
        for row in rows
    ]