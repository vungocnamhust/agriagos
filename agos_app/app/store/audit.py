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


def query_audit_logs(
    target_type: str | None = None,
    target_id: str | None = None,
    action_name: str | None = None,
    decision: str | None = None,
    reason_code: str | None = None,
    correlation_id: str | None = None,
    actor_id: str | None = None,
    actor_role: str | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return memory.query_audit_logs(
            target_type=target_type,
            target_id=target_id,
            action_name=action_name,
            decision=decision,
            reason_code=reason_code,
            correlation_id=correlation_id,
            actor_id=actor_id,
            actor_role=actor_role,
            created_from=created_from,
            created_to=created_to,
        )

    where_clauses: list[str] = []
    params: dict[str, Any] = {}
    if target_type is not None:
        where_clauses.append("target_type = :target_type")
        params["target_type"] = target_type
    if target_id is not None:
        where_clauses.append("target_id = :target_id")
        params["target_id"] = target_id
    if action_name is not None:
        where_clauses.append("action_name = :action_name")
        params["action_name"] = action_name
    if decision is not None:
        where_clauses.append("decision = :decision")
        params["decision"] = decision
    if reason_code is not None:
        where_clauses.append("reason_code = :reason_code")
        params["reason_code"] = reason_code
    if correlation_id is not None:
        where_clauses.append("correlation_id = :correlation_id")
        params["correlation_id"] = correlation_id
    if actor_id is not None:
        where_clauses.append("actor_id = :actor_id")
        params["actor_id"] = actor_id
    if actor_role is not None:
        where_clauses.append("actor_role = :actor_role")
        params["actor_role"] = actor_role
    if created_from is not None:
        where_clauses.append("created_at >= CAST(:created_from AS timestamptz)")
        params["created_from"] = created_from
    if created_to is not None:
        where_clauses.append("created_at <= CAST(:created_to AS timestamptz)")
        params["created_to"] = created_to

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    with _db.read_session() as session:
        rows = session.execute(
            text(
                f"""
                SELECT
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
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC, audit_id DESC
                """
            ),
            params,
        ).mappings().all()

    return [
        {
            "auditId": str(row["audit_id"]),
            "actorId": row["actor_id"],
            "actorRole": row["actor_role"],
            "actionName": row["action_name"],
            "targetType": row["target_type"],
            "targetId": row["target_id"],
            "decision": row["decision"],
            "reasonCode": row["reason_code"],
            "beforeSnapshot": row["before_snapshot"],
            "afterSnapshot": row["after_snapshot"],
            "metadata": row["metadata"] or {},
            "correlationId": row["correlation_id"],
            "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
        }
        for row in rows
    ]