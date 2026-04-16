# pyright: reportMissingImports=false
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


def _create_organization() -> str:
    response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Actor Org",
            "organizationType": "household_producer",
            "meta": {
                "correlationId": "corr-actor-org-create",
                "idempotencyKey": "idem-actor-org-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["organizationId"]


def _create_project_scope(organization_id: str) -> str:
    response = client.post(
        "/api/v1/projects",
        json={
            "organizationId": organization_id,
            "name": "Actor Project",
            "projectScopeType": "value_stream",
            "meta": {
                "correlationId": "corr-actor-project-create",
                "idempotencyKey": "idem-actor-project-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["projectScopeId"]


def test_actor_identity_and_affiliation_routes_support_create_get_and_create_affiliation() -> None:
    organization_id = _create_organization()
    project_scope_id = _create_project_scope(organization_id)

    created = client.post(
        "/api/v1/actors",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
        json={
            "actorType": "person",
            "displayName": "Tran Van A",
            "primaryPhone": "0900000600",
            "primaryEmail": "actor@example.com",
            "externalMappingsJson": {"crmContactId": "crm-actor-1"},
            "metadata": {"source": "manual"},
            "meta": {
                "correlationId": "corr-actor-create",
                "idempotencyKey": "idem-actor-create",
            },
        },
    )

    assert created.status_code == 201
    actor = created.json()["data"]
    assert actor["actorCode"].startswith("ACT-")
    assert actor["status"] == "active"

    detail = client.get(
        f"/api/v1/actors/{actor['actorId']}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert detail.status_code == 200
    assert detail.json()["displayName"] == "Tran Van A"

    affiliation = client.post(
        "/api/v1/affiliations",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
        json={
            "actorId": actor["actorId"],
            "organizationId": organization_id,
            "projectScopeId": project_scope_id,
            "affiliationKind": "membership",
            "effectiveAt": "2026-04-16T10:00:00Z",
            "metadata": {"note": "core-team"},
            "meta": {
                "correlationId": "corr-affiliation-create",
                "idempotencyKey": "idem-affiliation-create",
            },
        },
    )

    assert affiliation.status_code == 201
    affiliation_body = affiliation.json()["data"]
    assert affiliation_body["actorId"] == actor["actorId"]
    assert affiliation_body["organizationId"] == organization_id
    assert affiliation_body["projectScopeId"] == project_scope_id
    assert affiliation_body["status"] == "active"

    assert [event["eventName"] for event in memory.list_events()] == [
        "organization.created",
        "project_scope.created",
        "actor_identity.created",
        "actor_affiliation.created",
    ]


def test_actor_affiliation_route_requires_at_least_one_scope_anchor() -> None:
    created = client.post(
        "/api/v1/actors",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
        json={
            "actorType": "person",
            "displayName": "No Anchor Actor",
            "meta": {
                "correlationId": "corr-actor-no-anchor-create",
                "idempotencyKey": "idem-actor-no-anchor-create",
            },
        },
    )
    assert created.status_code == 201

    response = client.post(
        "/api/v1/affiliations",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
        json={
            "actorId": created.json()["data"]["actorId"],
            "affiliationKind": "observer",
            "effectiveAt": "2026-04-16T10:00:00Z",
            "meta": {
                "correlationId": "corr-affiliation-no-anchor",
                "idempotencyKey": "idem-affiliation-no-anchor",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "organizationId or projectScopeId is required."


def test_actor_routes_reject_unauthorized_roles() -> None:
    forbidden_create = client.post(
        "/api/v1/actors",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
        json={
            "actorType": "person",
            "displayName": "Unauthorized Actor",
            "meta": {
                "correlationId": "corr-actor-create-denied",
                "idempotencyKey": "idem-actor-create-denied",
            },
        },
    )

    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["code"] == "FORBIDDEN"