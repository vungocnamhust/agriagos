"""Project contribution store operations."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text

from app.models.enums import ProjectContributionVerificationSource, ProjectContributionVerificationStatus
from app.store import _db


def _build_metadata_json(record: dict[str, Any]) -> str:
    metadata = dict(record.get("metadata") or {})
    verification_metadata = {
        "actorType": record.get("actorType", "person"),
        "verificationStatus": record.get(
            "verificationStatus",
            ProjectContributionVerificationStatus.self_reported.value,
        ),
        "verificationSource": record.get(
            "verificationSource",
            ProjectContributionVerificationSource.manual_submission.value,
        ),
        "verificationNote": record.get("verificationNote"),
        "verificationEvidenceRef": record.get("verificationEvidenceRef"),
    }
    metadata.update({key: value for key, value in verification_metadata.items() if value is not None})
    return json.dumps(metadata)


def upsert_project_contribution(record: dict[str, Any]) -> None:
    if not _db.is_enabled():
        return

    with _db.write_session() as (session, should_commit):
        session.execute(
            text(
                """
                INSERT INTO project_contribution_events (
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    confirmed_by,
                    confirmed_at,
                    rejection_reason,
                    source,
                    metadata_json,
                    created_at,
                    updated_at
                ) VALUES (
                    :project_contribution_event_id,
                    :project_scope_id,
                    :project_assignment_id,
                    :organization_id,
                    :actor_id,
                    :subject_type,
                    :subject_id,
                    :contribution_type,
                    :role,
                    :quantity,
                    :unit,
                    :estimated_value,
                    :currency,
                    :status,
                    :confirmed_by,
                    :confirmed_at,
                    :rejection_reason,
                    :source,
                    CAST(:metadata_json AS jsonb),
                    :created_at,
                    now()
                )
                ON CONFLICT (project_contribution_event_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    confirmed_by = EXCLUDED.confirmed_by,
                    confirmed_at = EXCLUDED.confirmed_at,
                    rejection_reason = EXCLUDED.rejection_reason,
                    metadata_json = EXCLUDED.metadata_json,
                    updated_at = now()
                """
            ),
            {
                "project_contribution_event_id": record["projectContributionEventId"],
                "project_scope_id": record["projectScopeId"],
                "project_assignment_id": record["projectAssignmentId"],
                "organization_id": record["organizationId"],
                "actor_id": record["actorId"],
                "subject_type": record["subjectType"],
                "subject_id": record["subjectId"],
                "contribution_type": record["contributionType"],
                "role": record["role"],
                "quantity": record["quantity"],
                "unit": record["unit"],
                "estimated_value": record.get("estimatedValue"),
                "currency": record.get("currency"),
                "status": record["status"],
                "confirmed_by": record.get("confirmedBy"),
                "confirmed_at": record.get("confirmedAt"),
                "rejection_reason": record.get("rejectionReason"),
                "source": record.get("source", "manual"),
                "metadata_json": _build_metadata_json(record),
                "created_at": record.get("createdAt"),
            },
        )
        if should_commit:
            session.commit()


def list_project_contributions(project_scope_id: str) -> list[dict[str, Any]]:
    if not _db.is_enabled():
        return []

    with _db.read_session() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    confirmed_by,
                    confirmed_at,
                    rejection_reason,
                    source,
                    metadata_json,
                    created_at
                FROM project_contribution_events
                WHERE project_scope_id = :project_scope_id
                ORDER BY created_at, project_contribution_event_id
                """
            ),
            {"project_scope_id": project_scope_id},
        ).mappings().all()
    return [_map_project_contribution_row(row) for row in rows]


def fetch_project_contribution(project_contribution_event_id: str) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.read_session() as session:
        row = session.execute(
            text(
                """
                SELECT
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    confirmed_by,
                    confirmed_at,
                    rejection_reason,
                    source,
                    metadata_json,
                    created_at
                FROM project_contribution_events
                WHERE project_contribution_event_id = :project_contribution_event_id
                """
            ),
            {"project_contribution_event_id": project_contribution_event_id},
        ).mappings().first()
    if row is None:
        return None
    return _map_project_contribution_row(row)


def transition_project_contribution_from_proposed(record: dict[str, Any]) -> dict[str, Any] | None:
    if not _db.is_enabled():
        return None

    with _db.write_session() as (session, should_commit):
        row = session.execute(
            text(
                """
                UPDATE project_contribution_events
                SET
                    status = :status,
                    confirmed_by = :confirmed_by,
                    confirmed_at = :confirmed_at,
                    rejection_reason = :rejection_reason,
                    metadata_json = CAST(:metadata_json AS jsonb),
                    updated_at = now()
                WHERE project_contribution_event_id = :project_contribution_event_id
                  AND status = 'proposed'
                RETURNING
                    project_contribution_event_id,
                    project_scope_id,
                    project_assignment_id,
                    organization_id,
                    actor_id,
                    subject_type,
                    subject_id,
                    contribution_type,
                    role,
                    quantity,
                    unit,
                    estimated_value,
                    currency,
                    status,
                    confirmed_by,
                    confirmed_at,
                    rejection_reason,
                    source,
                    metadata_json,
                    created_at
                """
            ),
            {
                "project_contribution_event_id": record["projectContributionEventId"],
                "status": record["status"],
                "confirmed_by": record.get("confirmedBy"),
                "confirmed_at": record.get("confirmedAt"),
                "rejection_reason": record.get("rejectionReason"),
                "metadata_json": _build_metadata_json(record),
            },
        ).mappings().first()
        if row is None:
            return None
        if should_commit:
            session.commit()
    return _map_project_contribution_row(row)


def _map_project_contribution_row(row: Mapping[Any, Any]) -> dict[str, Any]:
    metadata = dict(row["metadata_json"] or {})
    return {
        "projectContributionEventId": str(row["project_contribution_event_id"]),
        "projectScopeId": str(row["project_scope_id"]),
        "projectAssignmentId": str(row["project_assignment_id"]),
        "organizationId": str(row["organization_id"]),
        "actorId": str(row["actor_id"]),
        "actorType": metadata.get("actorType", "person"),
        "subjectType": row["subject_type"],
        "subjectId": str(row["subject_id"]),
        "contributionType": row["contribution_type"],
        "role": row["role"],
        "verificationStatus": metadata.get(
            "verificationStatus",
            ProjectContributionVerificationStatus.self_reported.value,
        ),
        "verificationSource": metadata.get(
            "verificationSource",
            ProjectContributionVerificationSource.manual_submission.value,
        ),
        "verificationNote": metadata.get("verificationNote"),
        "verificationEvidenceRef": metadata.get("verificationEvidenceRef"),
        "quantity": _db.to_float(row["quantity"]),
        "unit": row["unit"],
        "estimatedValue": _db.to_float(row["estimated_value"]) if row["estimated_value"] is not None else None,
        "currency": row["currency"],
        "status": row["status"],
        "confirmedBy": str(row["confirmed_by"]) if row["confirmed_by"] is not None else None,
        "confirmedAt": row["confirmed_at"].isoformat() if row["confirmed_at"] else None,
        "rejectionReason": row["rejection_reason"],
        "source": row["source"],
        "metadata": metadata,
        "createdAt": row["created_at"].isoformat() if row["created_at"] else None,
    }