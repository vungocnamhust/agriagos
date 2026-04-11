"""Audit log storage for deterministic-core write decisions."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.store import _db
from app.store import memory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_audit_log(entry: dict[str, Any]) -> dict[str, Any]:
    audit_entry = {
        "auditId": entry.get("auditId", str(uuid.uuid4())),
        "actorId": entry.get("actorId"),
        "actorRole": entry.get("actorRole"),
        "actionName": entry["actionName"],
        "targetType": entry["targetType"],
        "targetId": entry["targetId"],
        "decision": entry["decision"],
        "reasonCode": entry.get("reasonCode"),
        "beforeSnapshot": entry.get("beforeSnapshot"),
        "afterSnapshot": entry.get("afterSnapshot"),
        "metadata": dict(entry.get("metadata", {})),
        "correlationId": entry.get("correlationId"),
        "createdAt": entry.get("createdAt", _now_iso()),
    }

    if not _db.is_enabled():
        return memory.append_audit_log(audit_entry)

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO audit_logs (
                    audit_id,
                    actor_id,
                    actor_role,
                    action_name,
                    target_type,
                    target_id,
                    decision,
                    reason_code,
                    before_snapshot,
                    after_snapshot,
                    metadata,
                    correlation_id,
                    created_at
                ) VALUES (
                    :audit_id,
                    :actor_id,
                    :actor_role,
                    :action_name,
                    :target_type,
                    :target_id,
                    :decision,
                    :reason_code,
                    CAST(:before_snapshot AS jsonb),
                    CAST(:after_snapshot AS jsonb),
                    CAST(:metadata AS jsonb),
                    :correlation_id,
                    CAST(:created_at AS timestamptz)
                )
                """
            ),
            {
                "audit_id": audit_entry["auditId"],
                "actor_id": audit_entry.get("actorId"),
                "actor_role": audit_entry.get("actorRole"),
                "action_name": audit_entry["actionName"],
                "target_type": audit_entry["targetType"],
                "target_id": audit_entry["targetId"],
                "decision": audit_entry["decision"],
                "reason_code": audit_entry.get("reasonCode"),
                "before_snapshot": json.dumps(audit_entry.get("beforeSnapshot")),
                "after_snapshot": json.dumps(audit_entry.get("afterSnapshot")),
                "metadata": json.dumps(audit_entry.get("metadata", {})),
                "correlation_id": audit_entry.get("correlationId"),
                "created_at": audit_entry["createdAt"],
            },
        )
        if should_commit:
            session.commit()

    return audit_entry