"""Helpers for deterministic-core write context, hashing, and audit decisions."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.store import audit as audit_store


def meta_context(meta: Any | None) -> dict[str, Any]:
    from app.core.authz import build_auth_context

    return build_auth_context(meta).to_context_dict()


def build_request_hash(payload: Any, *, extra: dict[str, Any] | None = None) -> str:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump(mode="json", exclude={"meta"}, exclude_none=False)
    else:
        data = payload

    if extra:
        data = {
            "context": extra,
            "payload": data,
        }

    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def append_audit_decision(
    *,
    action_name: str,
    target_type: str,
    target_id: str,
    decision: str,
    context: dict[str, Any],
    before_snapshot: Any | None = None,
    after_snapshot: Any | None = None,
    reason_code: str | None = None,
    event: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    audit_metadata = {
        "idempotencyKey": context.get("idempotency_key"),
        "externalRef": context.get("external_ref"),
    }
    if event is not None:
        audit_metadata.update(
            {
                "eventId": event.get("eventId"),
                "eventName": event.get("eventName"),
                "eventType": event.get("eventType"),
            }
        )
    if metadata:
        audit_metadata.update(metadata)

    return audit_store.append_audit_log(
        {
            "actorId": context.get("actor_id"),
            "actorRole": context.get("actor_role"),
            "actionName": action_name,
            "targetType": target_type,
            "targetId": target_id,
            "decision": decision,
            "reasonCode": reason_code,
            "beforeSnapshot": before_snapshot,
            "afterSnapshot": after_snapshot,
            "metadata": audit_metadata,
            "correlationId": context.get("correlation_id"),
        }
    )