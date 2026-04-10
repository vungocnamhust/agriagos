from fastapi import APIRouter

from app.store import memory as store

router = APIRouter()


@router.get("")
def list_events(
    aggregateType: str | None = None,
    aggregateId: str | None = None,
    eventName: str | None = None,
    correlationId: str | None = None,
) -> dict:
    items = store.query_events(
        aggregate_type=aggregateType,
        aggregate_id=aggregateId,
        event_name=eventName,
        correlation_id=correlationId,
    )
    return {"items": items, "total": len(items)}
