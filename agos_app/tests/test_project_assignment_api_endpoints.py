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
            "projectScopeCode": "PRJ-202604-0001",
            "name": "Lua mua 2026",
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def test_project_assignment_routes_create_list_and_end_assignments_for_supported_targets() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000a101"
    _seed_project_scope(project_scope_id)
    memory.save_plot(
        "00000000-0000-0000-0000-00000000b101",
        {
            "plotId": "00000000-0000-0000-0000-00000000b101",
            "plotCode": "PLOT-001",
            "organizationId": "org-1",
            "name": "Vuon A1",
            "areaValue": 2.5,
            "areaUnit": "ha",
            "status": "active",
        },
    )
    memory.save_crop_cycle(
        "00000000-0000-0000-0000-00000000c101",
        {
            "cropCycleId": "00000000-0000-0000-0000-00000000c101",
            "plotId": "00000000-0000-0000-0000-00000000b101",
            "organizationId": "org-1",
            "cropName": "Lua",
            "growthStage": "maturing",
            "status": "active",
        },
    )
    memory.save_lot(
        "00000000-0000-0000-0000-00000000d101",
        {
            "lotId": "00000000-0000-0000-0000-00000000d101",
            "organizationId": "org-1",
            "lotCode": "LOT-001",
            "status": "released",
        },
    )
    memory.save_preorder(
        "00000000-0000-0000-0000-00000000e101",
        {
            "preorderId": "00000000-0000-0000-0000-00000000e101",
            "organizationId": "org-1",
            "preorderCode": "DT-001",
            "status": "active",
        },
    )
    memory.save_order(
        "00000000-0000-0000-0000-00000000f101",
        {
            "orderId": "00000000-0000-0000-0000-00000000f101",
            "organizationId": "org-1",
            "orderCode": "ORD-001",
            "status": "confirmed",
        },
    )

    target_types = [
        ("plot", "00000000-0000-0000-0000-00000000b101"),
        ("crop_cycle", "00000000-0000-0000-0000-00000000c101"),
        ("lot", "00000000-0000-0000-0000-00000000d101"),
        ("preorder", "00000000-0000-0000-0000-00000000e101"),
        ("order", "00000000-0000-0000-0000-00000000f101"),
    ]

    created_ids: list[str] = []
    for index, (target_type, target_id) in enumerate(target_types):
        response = client.post(
            f"/api/v1/projects/{project_scope_id}/assignments",
            json={
                "targetType": target_type,
                "targetId": target_id,
                "isPrimary": index == 0,
                "attributionWeight": 1.0 if index == 0 else 0.5,
                "meta": {
                    "correlationId": f"corr-project-assignment-create-{index}",
                    "idempotencyKey": f"idem-project-assignment-create-{index}",
                    "actorId": "admin-1",
                    "actorRole": "admin",
                },
            },
        )
        assert response.status_code == 201
        created_ids.append(response.json()["data"]["projectAssignmentId"])

    list_response = client.get(
        f"/api/v1/projects/{project_scope_id}/assignments",
        headers=_auth_headers(actor_role="admin", actor_id="admin-1"),
    )
    assert list_response.status_code == 200
    assert [item["targetType"] for item in list_response.json()["items"]] == [item[0] for item in target_types]

    end_response = client.post(
        f"/api/v1/projects/{project_scope_id}/assignments/{created_ids[0]}/end",
        json={
            "reason": "season closed",
            "meta": {
                "correlationId": "corr-project-assignment-end",
                "idempotencyKey": "idem-project-assignment-end",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert end_response.status_code == 200
    assert end_response.json()["data"]["endedReason"] == "season closed"
    assert end_response.json()["data"]["endedAt"] is not None

    assert [event["eventName"] for event in memory.list_events()] == [
        "project_assignment.created",
        "project_assignment.created",
        "project_assignment.created",
        "project_assignment.created",
        "project_assignment.created",
        "project_assignment.ended",
    ]


def test_project_assignment_routes_reject_unknown_targets_and_unauthorized_reads() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000a102"
    _seed_project_scope(project_scope_id)

    not_found_response = client.post(
        f"/api/v1/projects/{project_scope_id}/assignments",
        json={
            "targetType": "plot",
            "targetId": "00000000-0000-0000-0000-00000000b199",
            "meta": {
                "correlationId": "corr-project-assignment-missing",
                "idempotencyKey": "idem-project-assignment-missing",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert not_found_response.status_code == 404

    forbidden_read = client.get(
        f"/api/v1/projects/{project_scope_id}/assignments",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )
    assert forbidden_read.status_code == 403
    assert forbidden_read.json()["code"] == "FORBIDDEN"


def test_project_assignment_audit_captures_authority_context_for_allow_and_deny() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000a103"
    plot_id = "00000000-0000-0000-0000-00000000b103"
    _seed_project_scope(project_scope_id)
    memory.save_plot(
        plot_id,
        {
            "plotId": plot_id,
            "plotCode": "PLOT-103",
            "organizationId": "org-1",
            "name": "Vuon B3",
            "areaValue": 1.5,
            "areaUnit": "ha",
            "status": "active",
        },
    )

    allowed = client.post(
        f"/api/v1/projects/{project_scope_id}/assignments",
        json={
            "targetType": "plot",
            "targetId": plot_id,
            "meta": {
                "correlationId": "corr-project-assignment-audit-allow",
                "idempotencyKey": "idem-project-assignment-audit-allow",
                "actorId": "admin-1",
                "actorRole": "admin",
                "delegatedActorId": "principal-1",
                "delegatedActorRole": "viewer",
            },
        },
    )

    assert allowed.status_code == 201
    allowed_audit = memory.list_audit_logs()[-1]
    assert allowed_audit["actionName"] == "project_assignment.create"
    assert allowed_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert allowed_audit["metadata"]["effectiveActorRole"] == "admin"
    assert allowed_audit["metadata"]["delegatedActorId"] == "principal-1"
    assert allowed_audit["metadata"]["delegatedActorRole"] == "viewer"

    denied = client.post(
        f"/api/v1/projects/{project_scope_id}/assignments",
        json={
            "targetType": "plot",
            "targetId": plot_id,
            "meta": {
                "correlationId": "corr-project-assignment-audit-deny",
                "idempotencyKey": "idem-project-assignment-audit-deny",
                "actorId": "sales-1",
                "actorRole": "sales",
                "delegatedActorId": "principal-2",
                "delegatedActorRole": "accountant",
            },
        },
    )

    assert denied.status_code == 403
    denied_audit = memory.list_audit_logs()[-1]
    assert denied_audit["reasonCode"] == "forbidden_project_assignment_write"
    assert denied_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert denied_audit["metadata"]["effectiveActorRole"] == "sales"
    assert denied_audit["metadata"]["delegatedActorId"] == "principal-2"
    assert denied_audit["metadata"]["delegatedActorRole"] == "accountant"


def test_project_assignment_rejects_cross_organization_targets() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000a104"
    plot_id = "00000000-0000-0000-0000-00000000b104"
    _seed_project_scope(project_scope_id)
    memory.save_plot(
        plot_id,
        {
            "plotId": plot_id,
            "plotCode": "PLOT-104",
            "organizationId": "org-2",
            "name": "Vuon C4",
            "areaValue": 2.0,
            "areaUnit": "ha",
            "status": "active",
        },
    )

    response = client.post(
        f"/api/v1/projects/{project_scope_id}/assignments",
        json={
            "targetType": "plot",
            "targetId": plot_id,
            "meta": {
                "correlationId": "corr-project-assignment-org-mismatch",
                "idempotencyKey": "idem-project-assignment-org-mismatch",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 422
    assert response.json()["message"] == "Project assignment target must belong to the same organization as the project scope."
    audit = memory.list_audit_logs()[-1]
    assert audit["reasonCode"] == "project_assignment_target_organization_mismatch"
    assert audit["metadata"]["scopeOrganizationId"] == "org-1"
    assert audit["metadata"]["targetOrganizationId"] == "org-2"
