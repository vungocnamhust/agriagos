from __future__ import annotations

from typing import Any

from app.core.authz import normalize_actor_role


def build_authority_audit_metadata(context: dict[str, Any]) -> dict[str, Any]:
    return {
        "authorityBasis": "runtime_role",
        "effectiveActorRole": context.get("normalized_actor_role") or normalize_actor_role(context.get("actor_role")),
        "delegatedActorId": context.get("delegated_actor_id"),
        "delegatedActorRole": context.get("delegated_actor_role"),
        "bypassRequested": context.get("bypass_requested", False),
    }