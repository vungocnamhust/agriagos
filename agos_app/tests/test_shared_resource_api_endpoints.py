# pyright: reportMissingImports=false
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def _auth_headers(*, actor_role: str, actor_id: str = "actor-1") -> dict[str, str]:
    return {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }


def test_shared_resource_routes_support_create_list_and_get() -> None:
    run_suffix = uuid.uuid4().hex
    create_response = client.post(
        "/api/v1/shared-resources",
        json={
            "organizationId": "org-1",
            "name": "Warehouse A",
            "resourceType": "warehouse",
            "capacityValue": 40.0,
            "capacityUnit": "ton",
            "description": "Shared dry warehouse",
            "meta": {
                "correlationId": f"corr-shared-resource-create-{run_suffix}",
                "idempotencyKey": f"idem-shared-resource-create-{run_suffix}",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert create_response.status_code == 201
    shared_resource = create_response.json()["data"]
    assert shared_resource["resourceCode"].startswith("RES-")
    assert shared_resource["status"] == "draft"
    assert shared_resource["resourceType"] == "warehouse"

    list_response = client.get(
        "/api/v1/shared-resources",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert list_response.status_code == 200
    assert [item["sharedResourceId"] for item in list_response.json()["items"]] == [
        shared_resource["sharedResourceId"]
    ]

    detail_response = client.get(
        f"/api/v1/shared-resources/{shared_resource['sharedResourceId']}",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["description"] == "Shared dry warehouse"
    assert detail_response.json()["capacityValue"] == 40.0
    assert [event["eventName"] for event in memory.list_events()] == ["shared_resource.created"]


def test_shared_resource_routes_reject_unauthorized_roles() -> None:
    denied_suffix = uuid.uuid4().hex
    forbidden_create = client.post(
        "/api/v1/shared-resources",
        json={
            "organizationId": "org-1",
            "name": "Unauthorized Van",
            "resourceType": "vehicle",
            "meta": {
                "correlationId": f"corr-shared-resource-create-denied-{denied_suffix}",
                "idempotencyKey": f"idem-shared-resource-create-denied-{denied_suffix}",
                "actorId": "sales-1",
                "actorRole": "sales",
            },
        },
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["code"] == "FORBIDDEN"

    allowed_suffix = uuid.uuid4().hex
    created = client.post(
        "/api/v1/shared-resources",
        json={
            "organizationId": "org-1",
            "name": "Allowed Van",
            "resourceType": "vehicle",
            "meta": {
                "correlationId": f"corr-shared-resource-create-allowed-{allowed_suffix}",
                "idempotencyKey": f"idem-shared-resource-create-allowed-{allowed_suffix}",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert created.status_code == 201

    forbidden_read = client.get(
        f"/api/v1/shared-resources/{created.json()['data']['sharedResourceId']}",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["code"] == "FORBIDDEN"


def test_shared_resource_create_is_idempotent() -> None:
    run_suffix = uuid.uuid4().hex
    payload = {
        "organizationId": "org-1",
        "name": "Marketing Budget Pool",
        "resourceType": "marketing_budget",
        "capacityValue": 10000000.0,
        "capacityUnit": "VND",
        "meta": {
            "correlationId": f"corr-shared-resource-idem-{run_suffix}",
            "idempotencyKey": f"idem-shared-resource-idem-{run_suffix}",
            "actorId": "admin-1",
            "actorRole": "admin",
        },
    }

    first_response = client.post("/api/v1/shared-resources", json=payload)
    second_response = client.post("/api/v1/shared-resources", json=payload)

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json() == first_response.json()
    assert [event["eventName"] for event in memory.list_events()] == ["shared_resource.created"]