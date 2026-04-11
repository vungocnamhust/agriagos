from typing import Any, Literal
from pydantic import BaseModel, Field

from app.models.enums import EventSource


class Meta(BaseModel):
    correlationId: str | None = None
    causationId: str | None = None
    actorId: str | None = None
    actorRole: str | None = None
    idempotencyKey: str | None = None
    externalRef: str | None = None  # for integration idempotency (08-integration-contracts.md)


class CommandMetaRequest(BaseModel):
    meta: Meta | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlationId: str | None = None
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    checks: dict[str, str] = Field(default_factory=dict)


class DomainEvent(BaseModel):
    eventId: str
    eventName: str
    eventType: str
    eventVersion: int = 1
    aggregateType: str
    aggregateId: str
    occurredAt: str
    actorType: Literal["user", "system", "agent", "integration"]
    actorId: str | None = None
    correlationId: str | None = None
    causationId: str | None = None
    idempotencyKey: str | None = None
    source: EventSource  # required: core | integration | system_job | agent (05-event-catalog.md)
    tenantId: str = "default"  # Phase 1 placeholder; not enforced until multi-tenant auth lands
    payload: dict[str, Any] = Field(default_factory=dict)


class DomainEventListResponse(BaseModel):
    items: list[DomainEvent]
    total: int
