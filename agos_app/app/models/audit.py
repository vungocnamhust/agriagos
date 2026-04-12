from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AuditLogEntry(BaseModel):
    auditId: str
    actorId: str | None = None
    actorRole: str | None = None
    actionName: str
    targetType: str
    targetId: str
    decision: Literal["allowed", "denied", "escalated", "failed"]
    reasonCode: str | None = None
    beforeSnapshot: dict[str, Any] | None = None
    afterSnapshot: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    correlationId: str | None = None
    createdAt: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogEntry]
    total: int