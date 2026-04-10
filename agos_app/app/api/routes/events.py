from fastapi import APIRouter

router = APIRouter()

@router.get("")
def list_events(
    aggregateType: str | None = None,
    aggregateId: str | None = None,
    eventName: str | None = None,
    correlationId: str | None = None,
) -> dict:
    # TODO: query domain event store
    return {"items": []}
