from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
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
            "subjectType": "lot",
            "subjectId": "lot-1",
            "contributionType": "labor_day",
            "role": "producer",
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

    listed = client.get(
        f"/api/v1/projects/{project_scope_id}/contributions",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["projectContributionEventId"] == contribution["projectContributionEventId"]

    confirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/contributions/{contribution['projectContributionEventId']}/confirm",
        json={
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