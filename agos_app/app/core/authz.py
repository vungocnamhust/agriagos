from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException


ROLE_ALIASES = {
    "super_admin": "super_admin",
    "superadmin": "super_admin",
    "founder": "founder",
    "admin": "admin",
    "admin_van_hanh": "admin",
    "operations_admin": "admin",
    "sales": "sales",
    "cskh": "cskh",
    "customer_service": "cskh",
    "customer_success": "cskh",
    "integration": "integration",
    "ops": "ops",
    "ops_manager": "ops",
    "ops_lead": "ops",
    "farm_manager": "farm_manager",
    "farm manager": "farm_manager",
    "accountant": "accountant",
    "viewer": "viewer",
    "viewer_analyst": "viewer",
    "agent": "agent",
    "automation": "agent",
    "qc_reviewer": "qc_reviewer",
    "qc reviewer": "qc_reviewer",
}


@dataclass(frozen=True)
class AuthContext:
    correlation_id: str | None = None
    causation_id: str | None = None
    actor_id: str | None = None
    actor_role: str | None = None
    normalized_actor_role: str | None = None
    idempotency_key: str | None = None
    external_ref: str | None = None
    bypass_requested: bool = False
    delegated_actor_id: str | None = None
    delegated_actor_role: str | None = None

    def to_context_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "normalized_actor_role": self.normalized_actor_role,
            "idempotency_key": self.idempotency_key,
            "external_ref": self.external_ref,
            "bypass_requested": self.bypass_requested,
            "delegated_actor_id": self.delegated_actor_id,
            "delegated_actor_role": self.delegated_actor_role,
        }


def normalize_actor_role(actor_role: str | None) -> str | None:
    if actor_role is None:
        return None
    normalized = actor_role.strip().lower().replace("/", " ").replace("-", " ")
    normalized = "_".join(normalized.split())
    return ROLE_ALIASES.get(normalized, normalized)


def build_auth_context(meta: Any | None) -> AuthContext:
    actor_role = getattr(meta, "actorRole", None)
    delegated_actor_role = getattr(meta, "delegatedActorRole", None)
    return AuthContext(
        correlation_id=getattr(meta, "correlationId", None),
        causation_id=getattr(meta, "causationId", None),
        actor_id=getattr(meta, "actorId", None),
        actor_role=actor_role,
        normalized_actor_role=normalize_actor_role(actor_role),
        idempotency_key=getattr(meta, "idempotencyKey", None),
        external_ref=getattr(meta, "externalRef", None),
        bypass_requested=bool(getattr(meta, "bypassRequested", False)),
        delegated_actor_id=getattr(meta, "delegatedActorId", None),
        delegated_actor_role=normalize_actor_role(delegated_actor_role),
    )


def ensure_bypass_permitted(
    *,
    action_name: str,
    target_type: str,
    target_id: str,
    context: AuthContext | dict[str, Any],
) -> None:
    from app.core.write_context import append_audit_decision

    if isinstance(context, AuthContext):
        context_dict = context.to_context_dict()
    else:
        context_dict = dict(context)

    if not context_dict.get("bypass_requested"):
        return

    append_audit_decision(
        action_name=action_name,
        target_type=target_type,
        target_id=target_id,
        decision="denied",
        context=context_dict,
        reason_code="agent_execution_not_allowed",
        metadata={
            "bypassRequested": True,
            "delegatedActorId": context_dict.get("delegated_actor_id"),
            "delegatedActorRole": context_dict.get("delegated_actor_role"),
        },
    )
    raise HTTPException(status_code=403, detail="Agent bypass lane is not enabled in Phase 1.")