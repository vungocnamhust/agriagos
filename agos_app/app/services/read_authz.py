from __future__ import annotations

from typing import Any, Iterable

from fastapi import HTTPException

from app.core.authz import ensure_bypass_permitted, normalize_actor_role
from app.core.policy_sets import PROJECT_SCOPED_EVENT_QUERY_ROLES, UNSCOPED_EVENT_QUERY_ROLES
from app.core.write_context import append_audit_decision, meta_context
from app.models.common import Meta


def _effective_actor_role(context: dict[str, Any], *, allow_delegated_agent: bool = True) -> str | None:
    actor_role = context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role"))
    if actor_role != "agent" or not allow_delegated_agent:
        return actor_role

    delegated_actor_role = normalize_actor_role(context.get("delegated_actor_role"))
    return delegated_actor_role or actor_role


def _deny_read(
    *,
    action_name: str,
    target_type: str,
    target_id: str,
    context: dict[str, Any],
    reason_code: str,
    detail: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    append_audit_decision(
        action_name=action_name,
        target_type=target_type,
        target_id=target_id,
        decision="denied",
        context=context,
        reason_code=reason_code,
        metadata=metadata,
    )
    raise HTTPException(status_code=403, detail=detail)


def authorize_read_surface(
    *,
    meta: Meta | None,
    action_name: str,
    target_type: str,
    target_id: str,
    allowed_roles: Iterable[str],
    reason_code: str,
    detail: str,
    allow_delegated_agent: bool = True,
) -> dict[str, Any]:
    context = meta_context(meta)
    ensure_bypass_permitted(
        action_name=action_name,
        target_type=target_type,
        target_id=target_id,
        context=context,
    )

    effective_actor_role = _effective_actor_role(context, allow_delegated_agent=allow_delegated_agent)
    if effective_actor_role not in set(allowed_roles):
        _deny_read(
            action_name=action_name,
            target_type=target_type,
            target_id=target_id,
            context=context,
            reason_code=reason_code,
            detail=detail,
            metadata={"effectiveActorRole": effective_actor_role},
        )

    return context


def authorize_scoped_event_query(
    *,
    meta: Meta | None,
    aggregate_type: str | None,
    aggregate_id: str | None,
    event_name: str | None,
    correlation_id: str | None,
    causation_id: str | None,
    idempotency_key: str | None,
) -> dict[str, Any]:
    context = meta_context(meta)
    ensure_bypass_permitted(
        action_name="event.query",
        target_type="EventStream",
        target_id="query",
        context=context,
    )

    effective_actor_role = _effective_actor_role(context)
    if effective_actor_role in UNSCOPED_EVENT_QUERY_ROLES:
        return context

    if effective_actor_role not in PROJECT_SCOPED_EVENT_QUERY_ROLES:
        _deny_read(
            action_name="event.query",
            target_type="EventStream",
            target_id="query",
            context=context,
            reason_code="forbidden_event_query",
            detail="Actor is not allowed to query the event stream.",
            metadata={"effectiveActorRole": effective_actor_role},
        )

    has_scope = any(
        value not in (None, "")
        for value in (aggregate_type, aggregate_id, event_name, correlation_id, causation_id, idempotency_key)
    )
    if not has_scope:
        _deny_read(
            action_name="event.query",
            target_type="EventStream",
            target_id="query",
            context=context,
            reason_code="event_scope_required",
            detail="Event queries for this role must include at least one scoping filter.",
            metadata={"effectiveActorRole": effective_actor_role},
        )

    return context