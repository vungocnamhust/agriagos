from datetime import datetime

from fastapi import APIRouter, Query

from app.models.audit import AuditLogEntry, AuditLogListResponse
from app.models.common import ErrorResponse
from app.services import audit as svc

router = APIRouter()


AUDIT_ERROR_RESPONSES = {
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.get("", response_model=AuditLogListResponse, responses=AUDIT_ERROR_RESPONSES)
def list_audit_logs(
    targetType: str | None = None,
    targetId: str | None = None,
    actionName: str | None = None,
    decision: str | None = Query(default=None, pattern="^(allowed|denied|escalated|failed)$"),
    reasonCode: str | None = None,
    correlationId: str | None = None,
    actorId: str | None = None,
    actorRole: str | None = None,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
) -> AuditLogListResponse:
    items = svc.query_audit_logs(
        target_type=targetType,
        target_id=targetId,
        action_name=actionName,
        decision=decision,
        reason_code=reasonCode,
        correlation_id=correlationId,
        actor_id=actorId,
        actor_role=actorRole,
        created_from=from_,
        created_to=to,
    )
    return AuditLogListResponse(items=[AuditLogEntry(**item) for item in items], total=len(items))