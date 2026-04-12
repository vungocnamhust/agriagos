from __future__ import annotations

from app.models.common import DomainEvent, DomainEventListResponse, Meta
from app.services.read_authz import authorize_scoped_event_query
from app.store import events as event_store


def list_events(
    *,
    aggregate_type: str | None,
    aggregate_id: str | None,
    event_name: str | None,
    correlation_id: str | None,
    causation_id: str | None,
    idempotency_key: str | None,
    meta: Meta | None,
) -> DomainEventListResponse:
    authorize_scoped_event_query(
        meta=meta,
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_name=event_name,
        correlation_id=correlation_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
    )

    items = event_store.query_events(
        aggregate_type=aggregate_type,
        aggregate_id=aggregate_id,
        event_name=event_name,
        correlation_id=correlation_id,
        causation_id=causation_id,
        idempotency_key=idempotency_key,
    )
    return DomainEventListResponse(items=[DomainEvent(**item) for item in items], total=len(items))