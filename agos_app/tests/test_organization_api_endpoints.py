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


def test_organization_routes_support_create_list_update_and_state_changes() -> None:
    create_response = client.post(
        "/api/v1/organizations",
        json={
            "name": "Hoang Gia Farm",
            "organizationType": "household_producer",
            "region": "Lam Dong",
            "representativeName": "Hoang Gia",
            "contactPhone": "0900000400",
            "meta": {"correlationId": "corr-org-create", "idempotencyKey": "idem-org-create", "actorId": "admin-1", "actorRole": "admin"},
        },
    )

    assert create_response.status_code == 201
    organization = create_response.json()["data"]
    assert organization["organizationCode"].startswith("ORG-")
    assert organization["status"] == "draft"

    list_response = client.get(
        "/api/v1/organizations",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert list_response.status_code == 200
    assert [item["organizationId"] for item in list_response.json()["items"]] == [organization["organizationId"]]

    detail_response = client.get(
        f"/api/v1/organizations/{organization['organizationId']}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["representativeName"] == "Hoang Gia"

    patch_response = client.patch(
        f"/api/v1/organizations/{organization['organizationId']}",
        json={
            "shortDescription": "Seed-to-sale household producer",
            "contactEmail": "hello@hoanggia.vn",
            "meta": {"correlationId": "corr-org-update", "idempotencyKey": "idem-org-update", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["data"]["contactEmail"] == "hello@hoanggia.vn"

    activate_response = client.post(
        f"/api/v1/organizations/{organization['organizationId']}/activate",
        json={"meta": {"correlationId": "corr-org-activate", "idempotencyKey": "idem-org-activate", "actorId": "admin-1", "actorRole": "admin"}},
    )
    assert activate_response.status_code == 200
    assert activate_response.json()["data"]["status"] == "active"

    pause_response = client.post(
        f"/api/v1/organizations/{organization['organizationId']}/pause",
        json={
            "reason": "Seasonal shutdown",
            "meta": {"correlationId": "corr-org-pause", "idempotencyKey": "idem-org-pause", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["data"]["status"] == "paused"

    close_response = client.post(
        f"/api/v1/organizations/{organization['organizationId']}/close",
        json={
            "reason": "Closed legal entity",
            "meta": {"correlationId": "corr-org-close", "idempotencyKey": "idem-org-close", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert close_response.status_code == 200
    assert close_response.json()["data"]["status"] == "closed"
    assert [event["eventName"] for event in memory.list_events()] == [
        "organization.created",
        "organization.updated",
        "organization.activated",
        "organization.paused",
        "organization.closed",
    ]


def test_organization_routes_reject_unauthorized_roles() -> None:
    forbidden_create = client.post(
        "/api/v1/organizations",
        json={
            "name": "Unauthorized Org",
            "organizationType": "family_business",
            "meta": {"correlationId": "corr-org-create-denied", "idempotencyKey": "idem-org-create-denied", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["code"] == "FORBIDDEN"

    created = client.post(
        "/api/v1/organizations",
        json={
            "name": "Allowed Org",
            "organizationType": "family_business",
            "meta": {"correlationId": "corr-org-create-allowed", "idempotencyKey": "idem-org-create-allowed", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert created.status_code == 201

    forbidden_read = client.get(
        f"/api/v1/organizations/{created.json()['data']['organizationId']}",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["code"] == "FORBIDDEN"


def test_organization_update_requires_mutable_fields() -> None:
    created = client.post(
        "/api/v1/organizations",
        json={
            "name": "Needs Update Fields",
            "organizationType": "solo_founder",
            "meta": {"correlationId": "corr-org-empty-update-create", "idempotencyKey": "idem-org-empty-update-create", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert created.status_code == 201

    empty_update = client.patch(
        f"/api/v1/organizations/{created.json()['data']['organizationId']}",
        json={
            "meta": {"correlationId": "corr-org-empty-update", "idempotencyKey": "idem-org-empty-update", "actorId": "admin-1", "actorRole": "admin"},
        },
    )
    assert empty_update.status_code == 422
    assert empty_update.json()["code"] == "VALIDATION_ERROR"