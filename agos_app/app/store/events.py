"""Domain event store operations."""
from __future__ import annotations

import json
import re
from typing import Any

from sqlalchemy import text

from app.store._db import SessionLocal, is_enabled
from app.store import memory

__all__ = ["append_event", "query_events"]


def _to_event_type(dotted_name: str) -> str:
    parts = re.split(r"[._]", dotted_name)
    return "".join(part.capitalize() for part in parts if part)


def append_event(event: dict[str, Any]) -> None:
    if not is_enabled():
        memory.append_event(event)
        return

    with SessionLocal() as session:
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
                    :source,
                    CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "event_id": event["eventId"],
                "tenant_id": event.get("tenantId", "default"),
                "event_name": event["eventName"],
                "event_version": 1,
                "aggregate_type": event["aggregateType"],
                "aggregate_id": event["aggregateId"],
                "occurred_at": event["occurredAt"],
                "actor_type": event["actorType"],
                "actor_id": event.get("actorId"),
                "correlation_id": event.get("correlationId"),
                "source": event.get("source", "core"),
                "payload": json.dumps(event.get("payload", {})),
            },
        )
        session.commit()


def query_events(
    aggregate_type: str | None = None,
    aggregate_id: str | None = None,
    event_name: str | None = None,
    correlation_id: str | None = None,
) -> list[dict[str, Any]]:
    if not is_enabled():
        return memory.query_events(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_name=event_name,
            correlation_id=correlation_id,
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

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with SessionLocal() as session:
        rows = session.execute(
            text(
                f"""
                SELECT
                    event_id,
                    tenant_id,
                    event_name,
                    aggregate_type,
                    aggregate_id,
                    occurred_at,
                    actor_type,
                    actor_id,
                    correlation_id,
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
            "aggregateType": row["aggregate_type"],
            "aggregateId": row["aggregate_id"],
            "occurredAt": row["occurred_at"].isoformat() if row["occurred_at"] else None,
            "actorType": row["actor_type"],
            "actorId": row["actor_id"],
            "correlationId": row["correlation_id"],
            "source": row["source"],
            "payload": row["payload"],
        }
        for row in rows
    ]