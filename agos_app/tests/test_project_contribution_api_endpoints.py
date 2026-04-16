from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.common import Meta
from app.models.project_contributions import RejectProjectContributionRequest
from app.services import project_contributions as project_contribution_service
from app.store import memory


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


def _seed_project_scope(project_scope_id: str) -> None:
    memory.save_project_scope(
        project_scope_id,
        {
            "projectScopeId": project_scope_id,
            "organizationId": "org-1",
            "projectScopeCode": "PRJ-202604-0099",
            "name": "Contribution Scope",
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def _seed_project_assignment(project_scope_id: str, assignment_id: str) -> None:
    memory.save_project_assignment(
        assignment_id,
        {
            "projectAssignmentId": assignment_id,
            "projectScopeId": project_scope_id,
            "targetType": "lot",
            "targetId": "lot-1",
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": None,
            "endedReason": None,
            "metadata": {},
        },
    )


def test_project_contribution_routes_record_list_confirm_and_reject() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b401"
    assignment_id = "00000000-0000-0000-0000-00000000b402"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)

    created = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "actorType": "person",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
            "verificationStatus": "system_detected",
            "verificationSource": "field_log",
            "verificationNote": "Imported from field ops note",
            "verificationEvidenceRef": "field-log-001",
            "quantity": 2,
            "unit": "day",
            "estimatedValue": 500000,
            "currency": "VND",
            "meta": {
                "correlationId": "corr-project-contribution-create",
                "idempotencyKey": "idem-project-contribution-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert created.status_code == 201
    contribution = created.json()["data"]
    assert contribution["status"] == "proposed"
    assert contribution["actorType"] == "person"
    assert contribution["verificationStatus"] == "system_detected"
    assert contribution["verificationSource"] == "field_log"
    assert contribution["verificationEvidenceRef"] == "field-log-001"

    listed = client.get(
        f"/api/v1/projects/{project_scope_id}/contributions",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["projectContributionEventId"] == contribution["projectContributionEventId"]

    confirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution['projectContributionEventId']}/confirm",
        json={
            "verificationNote": "Verified against supervisor checklist",
            "verificationEvidenceRef": "approval-001",
            "meta": {
                "correlationId": "corr-project-contribution-confirm",
                "idempotencyKey": "idem-project-contribution-confirm",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"
    assert confirmed.json()["data"]["verificationStatus"] == "verified"
    assert confirmed.json()["data"]["verificationSource"] == "admin_confirmed"
    assert confirmed.json()["data"]["verificationNote"] == "Verified against supervisor checklist"
    assert confirmed.json()["data"]["verificationEvidenceRef"] == "approval-001"

    second_created = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-2",
            "actorType": "partner",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "cash_support",
            "role": "supporter",
            "quantity": 1,
            "unit": "entry",
            "estimatedValue": 250000,
            "currency": "VND",
            "meta": {
                "correlationId": "corr-project-contribution-create-2",
                "idempotencyKey": "idem-project-contribution-create-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second_id = second_created.json()["data"]["projectContributionEventId"]

    rejected = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{second_id}/reject",
        json={
            "reason": "duplicate entry",
            "meta": {
                "correlationId": "corr-project-contribution-reject",
                "idempotencyKey": "idem-project-contribution-reject",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"
    assert rejected.json()["data"]["rejectionReason"] == "duplicate entry"
    assert rejected.json()["data"]["verificationStatus"] == "rejected"
    assert rejected.json()["data"]["verificationSource"] == "admin_rejected"
    assert rejected.json()["data"]["verificationNote"] == "duplicate entry"

    assert [event["eventName"] for event in memory.list_events()] == [
        "project_contribution.recorded",
        "project_contribution.confirmed",
        "project_contribution.recorded",
        "project_contribution.rejected",
    ]


def test_project_contribution_routes_reject_unknown_assignment_and_forbidden_reads() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b403"
    _seed_project_scope(project_scope_id)

    missing_assignment = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": "00000000-0000-0000-0000-00000000b499",
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
            "quantity": 1,
            "unit": "day",
            "estimatedValue": 100000,
            "currency": "VND",
            "meta": {
                "correlationId": "corr-project-contribution-missing",
                "idempotencyKey": "idem-project-contribution-missing",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert missing_assignment.status_code == 404

    forbidden_read = client.get(
        f"/api/v1/projects/{project_scope_id}/contributions",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["code"] == "FORBIDDEN"


def test_project_contribution_routes_reject_subject_mismatch() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b404"
    assignment_id = "00000000-0000-0000-0000-00000000b405"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)

    response = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "subjectType": "order",
            "subjectId": "order-1",
            "contributionType": "labor_day",
            "role": "producer",
            "quantity": 1,
            "unit": "day",
            "estimatedValue": 100000,
            "currency": "VND",
            "meta": {
                "correlationId": "corr-project-contribution-subject-mismatch",
                "idempotencyKey": "idem-project-contribution-subject-mismatch",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Contribution subject must match the project assignment target."


def test_project_contribution_routes_reject_terminal_and_conflicting_transitions() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b406"
    assignment_id = "00000000-0000-0000-0000-00000000b407"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)

    created = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
            "quantity": 1,
            "unit": "day",
            "meta": {
                "correlationId": "corr-project-contribution-terminal-create",
                "idempotencyKey": "idem-project-contribution-terminal-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    contribution_id = created.json()["data"]["projectContributionEventId"]

    confirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution_id}/confirm",
        json={
            "meta": {
                "correlationId": "corr-project-contribution-terminal-confirm",
                "idempotencyKey": "idem-project-contribution-terminal-confirm",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert confirmed.status_code == 200

    confirm_again = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution_id}/confirm",
        json={
            "meta": {
                "correlationId": "corr-project-contribution-terminal-confirm-again",
                "idempotencyKey": "idem-project-contribution-terminal-confirm-again",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert confirm_again.status_code == 422
    assert confirm_again.json()["message"] == "Project contribution is not confirmable."

    reject_confirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution_id}/reject",
        json={
            "reason": "late conflict",
            "meta": {
                "correlationId": "corr-project-contribution-terminal-reject-confirmed",
                "idempotencyKey": "idem-project-contribution-terminal-reject-confirmed",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert reject_confirmed.status_code == 422
    assert reject_confirmed.json()["message"] == "Project contribution is not rejectable."

    second_created = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-2",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "cash_support",
            "role": "supporter",
            "quantity": 1,
            "unit": "entry",
            "meta": {
                "correlationId": "corr-project-contribution-terminal-create-2",
                "idempotencyKey": "idem-project-contribution-terminal-create-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second_id = second_created.json()["data"]["projectContributionEventId"]

    rejected = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{second_id}/reject",
        json={
            "reason": "duplicate entry",
            "meta": {
                "correlationId": "corr-project-contribution-terminal-reject",
                "idempotencyKey": "idem-project-contribution-terminal-reject",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert rejected.status_code == 200

    reject_again = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{second_id}/reject",
        json={
            "reason": "duplicate entry",
            "meta": {
                "correlationId": "corr-project-contribution-terminal-reject-again",
                "idempotencyKey": "idem-project-contribution-terminal-reject-again",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert reject_again.status_code == 422
    assert reject_again.json()["message"] == "Project contribution is not rejectable."

    confirm_rejected = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{second_id}/confirm",
        json={
            "meta": {
                "correlationId": "corr-project-contribution-terminal-confirm-rejected",
                "idempotencyKey": "idem-project-contribution-terminal-confirm-rejected",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert confirm_rejected.status_code == 422
    assert confirm_rejected.json()["message"] == "Project contribution is not confirmable."


def test_project_contribution_audit_captures_authority_context_for_allow_and_deny() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b408"
    assignment_id = "00000000-0000-0000-0000-00000000b409"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)

    allowed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
            "quantity": 1,
            "unit": "day",
            "meta": {
                "correlationId": "corr-project-contribution-audit-allow",
                "idempotencyKey": "idem-project-contribution-audit-allow",
                "actorId": "admin-1",
                "actorRole": "admin",
                "delegatedActorId": "principal-1",
                "delegatedActorRole": "sales",
            },
        },
    )

    assert allowed.status_code == 201
    allowed_audit = memory.list_audit_logs()[-1]
    assert allowed_audit["actionName"] == "project_contribution.record"
    assert allowed_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert allowed_audit["metadata"]["effectiveActorRole"] == "admin"
    assert allowed_audit["metadata"]["delegatedActorId"] == "principal-1"
    assert allowed_audit["metadata"]["delegatedActorRole"] == "sales"

    denied = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-2",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "cash_support",
            "role": "supporter",
            "quantity": 1,
            "unit": "entry",
            "meta": {
                "correlationId": "corr-project-contribution-audit-deny",
                "idempotencyKey": "idem-project-contribution-audit-deny",
                "actorId": "sales-1",
                "actorRole": "sales",
                "delegatedActorId": "principal-2",
                "delegatedActorRole": "viewer",
            },
        },
    )

    assert denied.status_code == 403
    denied_audit = memory.list_audit_logs()[-1]
    assert denied_audit["reasonCode"] == "forbidden_project_contribution_write"
    assert denied_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert denied_audit["metadata"]["effectiveActorRole"] == "sales"
    assert denied_audit["metadata"]["delegatedActorId"] == "principal-2"
    assert denied_audit["metadata"]["delegatedActorRole"] == "viewer"


def test_project_contribution_memory_path_reject_does_not_overwrite_confirmed_record_after_stale_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000b410"
    assignment_id = "00000000-0000-0000-0000-00000000b411"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)

    created = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions",
        json={
            "projectAssignmentId": assignment_id,
            "organizationId": "org-1",
            "actorId": "farmer-1",
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
            "quantity": 1,
            "unit": "day",
            "meta": {
                "correlationId": "corr-project-contribution-memory-stale-create",
                "idempotencyKey": "idem-project-contribution-memory-stale-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    contribution_id = created.json()["data"]["projectContributionEventId"]

    confirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution_id}/confirm",
        json={
            "meta": {
                "correlationId": "corr-project-contribution-memory-stale-confirm",
                "idempotencyKey": "idem-project-contribution-memory-stale-confirm",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert confirmed.status_code == 200

    original_get = memory.get_project_contribution
    stale_record = {**created.json()["data"], "status": "proposed"}
    get_call_count = {"count": 0}

    def get_with_stale_first(project_contribution_event_id: str) -> dict[str, object] | None:
        if project_contribution_event_id == contribution_id and get_call_count["count"] == 0:
            get_call_count["count"] += 1
            return stale_record
        return original_get(project_contribution_event_id)

    monkeypatch.setattr(memory, "get_project_contribution", get_with_stale_first)

    with pytest.raises(HTTPException) as exc_info:
        project_contribution_service.reject_project_contribution(
            project_scope_id,
            contribution_id,
            RejectProjectContributionRequest(
                reason="stale conflicting reject",
                meta=Meta(
                    correlationId="corr-project-contribution-memory-stale-reject",
                    idempotencyKey="idem-project-contribution-memory-stale-reject",
                    actorId="admin-1",
                    actorRole="admin",
                ),
            ),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Project contribution is not rejectable."
    assert original_get(contribution_id)["status"] == "confirmed"