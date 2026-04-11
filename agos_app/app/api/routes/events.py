from fastapi import APIRouter

from app.models.common import DomainEvent, DomainEventListResponse
from app.store import events as store

router = APIRouter()


@router.get("", response_model=DomainEventListResponse)
def list_events(
    aggregateType: str | None = None,
    aggregateId: str | None = None,
    eventName: str | None = None,
    correlationId: str | None = None,
) -> DomainEventListResponse:
    items = store.query_events(
        aggregate_type=aggregateType,
        aggregate_id=aggregateId,
        event_name=eventName,
        correlation_id=correlationId,
    )
    return DomainEventListResponse(
        items=[DomainEvent(**e) for e in items],
        total=len(items),
    )
