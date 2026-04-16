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


def test_project_scope_routes_support_create_list_update_and_state_changes() -> None:
    create_response = client.post(
        "/api/v1/projects",
        json={
            "organizationId": "org-1",
            "name": "Lua mua 2026",
            "projectScopeType": "value_stream",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "description": "Value stream cho lua mua 2026",
            "meta": {"correlationId": "corr-project-create", "idempotencyKey": "idem-project-create", "actorId": "admin-1", "actorRole": "admin"},
        },
    )

    assert create_response.status_code == 201
    project_scope = create_response.json()["data"]
    assert project_scope["projectScopeCode"].startswith("PRJ-")
    assert project_scope["status"] == "draft"

    list_response = client.get(
        "/api/v1/projects",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert list_response.status_code == 200
    assert [item["projectScopeId"] for item in list_response.json()["items"]] == [project_scope["projectScopeId"]]

    detail_response = client.get(
        f"/api/v1/projects/{project_scope['projectScopeId']}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["seasonYear"] == "2026"

    patch_response = client.patch(
        f"/api/v1/projects/{project_scope['projectScopeId']}",
        json={
            "description": "Updated project scope",
            "metadata": {"channel": "seasonal"},
            "meta": {"correlationId": "corr-project-update", "idempotencyKey": "idem-project-update", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["description"] == "Updated project scope"
    assert patch_response.json()["data"]["metadata"]["channel"] == "seasonal"

    activate_response = client.post(
        f"/api/v1/projects/{project_scope['projectScopeId']}/activate",
        json={"meta": {"correlationId": "corr-project-activate", "idempotencyKey": "idem-project-activate", "actorId": "admin-1", "actorRole": "admin"}},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["status"] == "active"

    pause_response = client.post(
        f"/api/v1/projects/{project_scope['projectScopeId']}/pause",
        json={
            "reason": "Season complete",
            "meta": {"correlationId": "corr-project-pause", "idempotencyKey": "idem-project-pause", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["data"]["status"] == "paused"

    close_response = client.post(
        f"/api/v1/projects/{project_scope['projectScopeId']}/close",
        json={
            "reason": "Season delivered",
            "meta": {"correlationId": "corr-project-close", "idempotencyKey": "idem-project-close", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert close_response.status_code == 200
    assert close_response.json()["data"]["status"] == "closed"

    archive_response = client.post(
        f"/api/v1/projects/{project_scope['projectScopeId']}/archive",
        json={"meta": {"correlationId": "corr-project-archive", "idempotencyKey": "idem-project-archive", "actorId": "admin-1", "actorRole": "admin"}},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["data"]["status"] == "archived"
    assert [event["eventName"] for event in memory.list_events()] == [
        "project_scope.created",
        "project_scope.updated",
        "project_scope.activated",
        "project_scope.paused",
        "project_scope.closed",
        "project_scope.archived",
    ]


def test_project_scope_routes_reject_unauthorized_roles() -> None:
    forbidden_create = client.post(
        "/api/v1/projects",
        json={
            "organizationId": "org-1",
            "name": "Unauthorized Scope",
            "projectScopeType": "value_stream",
            "meta": {"correlationId": "corr-project-create-denied", "idempotencyKey": "idem-project-create-denied", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["code"] == "FORBIDDEN"

    created = client.post(
        "/api/v1/projects",
        json={
            "organizationId": "org-1",
            "name": "Allowed Scope",
            "projectScopeType": "campaign",
            "meta": {"correlationId": "corr-project-create-allowed", "idempotencyKey": "idem-project-create-allowed", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert created.status_code == 201

    forbidden_read = client.get(
        f"/api/v1/projects/{created.json()['data']['projectScopeId']}",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["code"] == "FORBIDDEN"


def test_project_scope_create_is_idempotent() -> None:
    payload = {
        "organizationId": "org-1",
        "name": "Honey 2026",
        "projectScopeType": "product_line",
        "seasonYear": "2026",
        "meta": {"correlationId": "corr-project-idem", "idempotencyKey": "idem-project-idem", "actorId": "admin-1", "actorRole": "admin"},
    }

    first_response = client.post("/api/v1/projects", json=payload)
    second_response = client.post("/api/v1/projects", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json() == first_response.json()
    assert [event["eventName"] for event in memory.list_events()] == ["project_scope.created"]


def test_project_scope_update_requires_mutable_fields() -> None:
    created = client.post(
        "/api/v1/projects",
        json={
            "organizationId": "org-1",
            "name": "Needs Update Fields",
            "projectScopeType": "shared_service",
            "meta": {"correlationId": "corr-project-empty-update-create", "idempotencyKey": "idem-project-empty-update-create", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert created.status_code == 201

    empty_update = client.patch(
        f"/api/v1/projects/{created.json()['data']['projectScopeId']}",
        json={
            "meta": {"correlationId": "corr-project-empty-update", "idempotencyKey": "idem-project-empty-update", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert empty_update.status_code == 422
    assert empty_update.json()["code"] == "VALIDATION_ERROR"
    assert memory.list_audit_logs()[-1]["actionName"] == "project_scope.update"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "empty_update_payload"