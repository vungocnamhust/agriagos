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


def _seed_project_scope(project_scope_id: str, *, organization_id: str = "org-1") -> None:
    memory.save_project_scope(
        project_scope_id,
        {
            "projectScopeId": project_scope_id,
            "organizationId": organization_id,
            "projectScopeCode": f"PRJ-{project_scope_id[-4:]}",
            "name": "Shared Resource Scope",
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def _create_shared_resource(*, capacity_value: float = 10.0, organization_id: str = "org-1") -> str:
    run_suffix = uuid.uuid4().hex
    response = client.post(
        "/api/v1/shared-resources",
        json={
            "organizationId": organization_id,
            "name": "Shared Van",
            "resourceType": "vehicle",
            "capacityValue": capacity_value,
            "capacityUnit": "slot",
            "description": "Allocated across scopes",
            "meta": {
                "correlationId": f"corr-shared-resource-seed-{run_suffix}",
                "idempotencyKey": f"idem-shared-resource-seed-{run_suffix}",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert response.status_code == 201
    return response.json()["data"]["sharedResourceId"]


def test_shared_resource_allocation_routes_allocate_and_release() -> None:
    shared_resource_id = _create_shared_resource(capacity_value=10.0)
    project_scope_id = "00000000-0000-0000-0000-00000000s501"
    _seed_project_scope(project_scope_id)

    allocated = client.post(
        f"/api/v1/shared-resources/{shared_resource_id}/allocations",
        json={
            "projectScopeId": project_scope_id,
            "allocationBasis": "manual",
            "allocatedCapacity": 4.0,
            "meta": {
                "correlationId": "corr-shared-resource-allocate",
                "idempotencyKey": "idem-shared-resource-allocate",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert allocated.status_code == 201
    allocation = allocated.json()["data"]
    assert allocation["sharedResourceId"] == shared_resource_id
    assert allocation["projectScopeId"] == project_scope_id
    assert allocation["allocatedCapacity"] == 4.0
    assert allocation["releasedCapacity"] == 0.0
    assert allocation["status"] == "active"

    released = client.post(
        f"/api/v1/shared-resources/{shared_resource_id}/allocations/{allocation['allocationId']}/release",
        json={
            "releasedCapacity": 4.0,
            "meta": {
                "correlationId": "corr-shared-resource-release",
                "idempotencyKey": "idem-shared-resource-release",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert released.status_code == 200
    released_payload = released.json()["data"]
    assert released_payload["releasedCapacity"] == 4.0
    assert released_payload["status"] == "released"
    assert [event["eventName"] for event in memory.list_events()] == [
        "shared_resource.created",
        "shared_resource.allocated",
        "shared_resource.released",
    ]


def test_shared_resource_allocation_rejects_capacity_overflow() -> None:
    shared_resource_id = _create_shared_resource(capacity_value=5.0)
    first_scope_id = "00000000-0000-0000-0000-00000000s502"
    second_scope_id = "00000000-0000-0000-0000-00000000s503"
    _seed_project_scope(first_scope_id)
    _seed_project_scope(second_scope_id)

    first = client.post(
        f"/api/v1/shared-resources/{shared_resource_id}/allocations",
        json={
            "projectScopeId": first_scope_id,
            "allocationBasis": "manual",
            "allocatedCapacity": 3.0,
            "meta": {
                "correlationId": "corr-shared-resource-overflow-1",
                "idempotencyKey": "idem-shared-resource-overflow-1",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second = client.post(
        f"/api/v1/shared-resources/{shared_resource_id}/allocations",
        json={
            "projectScopeId": second_scope_id,
            "allocationBasis": "manual",
            "allocatedCapacity": 3.0,
            "meta": {
                "correlationId": "corr-shared-resource-overflow-2",
                "idempotencyKey": "idem-shared-resource-overflow-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["message"] == "Shared resource allocation exceeds available capacity."


def test_shared_resource_allocation_rejects_cross_organization_scope() -> None:
    shared_resource_id = _create_shared_resource(capacity_value=5.0, organization_id="org-1")
    foreign_scope_id = "00000000-0000-0000-0000-00000000s504"
    _seed_project_scope(foreign_scope_id, organization_id="org-2")

    response = client.post(
        f"/api/v1/shared-resources/{shared_resource_id}/allocations",
        json={
            "projectScopeId": foreign_scope_id,
            "allocationBasis": "manual",
            "allocatedCapacity": 2.0,
            "meta": {
                "correlationId": "corr-shared-resource-cross-org",
                "idempotencyKey": "idem-shared-resource-cross-org",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Shared resource organization does not match the target project scope."