from fastapi import APIRouter, Request

from app.api.routes._meta import request_meta
from app.models.common import DomainEventListResponse, ErrorResponse
from app.services import events as svc

router = APIRouter()


@router.get("", response_model=DomainEventListResponse, responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def list_events(
    request: Request,
    aggregateType: str | None = None,
    aggregateId: str | None = None,
    eventName: str | None = None,
    correlationId: str | None = None,
    causationId: str | None = None,
    idempotencyKey: str | None = None,
) -> DomainEventListResponse:
    return svc.list_events(
        aggregate_type=aggregateType,
        aggregate_id=aggregateId,
        event_name=eventName,
        correlation_id=correlationId,
        causation_id=causationId,
        idempotency_key=idempotencyKey,
        meta=request_meta(request),
    )
