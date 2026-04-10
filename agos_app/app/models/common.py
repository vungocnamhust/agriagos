from typing import Any, Literal
from pydantic import BaseModel, Field

from app.models.enums import EventSource


class Meta(BaseModel):
    correlationId: str | None = None
    actorId: str | None = None
    actorRole: str | None = None
    idempotencyKey: str | None = None
    externalRef: str | None = None  # for integration idempotency (08-integration-contracts.md)


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlationId: str | None = None
    details: dict[str, Any] | None = None


class DomainEvent(BaseModel):
    eventId: str
    eventName: str
    aggregateType: str
    aggregateId: str
    occurredAt: str
    actorType: Literal["user", "system", "agent", "integration"]
    actorId: str | None = None
    correlationId: str | None = None
    source: EventSource  # required: core | integration | system_job | agent (05-event-catalog.md)
    payload: dict[str, Any] = Field(default_factory=dict)
