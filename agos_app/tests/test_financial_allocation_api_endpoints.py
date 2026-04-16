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


def _seed_project_scope(project_scope_id: str, *, name: str, code: str) -> None:
    memory.save_project_scope(
        project_scope_id,
        {
            "projectScopeId": project_scope_id,
            "organizationId": "org-1",
            "projectScopeCode": code,
            "name": name,
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def _seed_project_cost_record(
    cost_record_id: str,
    project_scope_id: str,
    *,
    amount: float = 450000.0,
    organization_id: str = "org-1",
) -> None:
    memory.save_project_cost_record(
        cost_record_id,
        {
            "costRecordId": cost_record_id,
            "projectScopeId": project_scope_id,
            "organizationId": organization_id,
            "costType": "labor_payout",
            "amount": amount,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": "contribution-1",
            "attributionPolicy": "direct_source_link",
            "metadata": {},
            "createdAt": memory.now_iso(),
        },
    )


def test_financial_allocation_routes_allocate_cost_and_list_allocations() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f401"
    target_scope_id = "00000000-0000-0000-0000-00000000f402"
    cost_record_id = "00000000-0000-0000-0000-00000000f403"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-001")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-001")
    _seed_project_cost_record(cost_record_id, source_scope_id)

    created = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-create",
                "idempotencyKey": "idem-fin-alloc-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert created.status_code == 201
    payload = created.json()["data"]
    assert payload["projectScopeId"] == target_scope_id
    assert payload["sourceRecordType"] == "cost_record"
    assert payload["sourceRecordId"] == cost_record_id
    assert payload["allocationBasis"] == "manual_full"
    assert payload["allocationWeight"] == 1.0
    assert payload["allocatedAmount"] == 450000.0
    assert payload["currency"] == "VND"

    listed = client.get(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )

    assert listed.status_code == 200
    assert listed.json()["items"][0]["financialAllocationId"] == payload["financialAllocationId"]


def test_financial_allocation_routes_reject_missing_source_record() -> None:
    target_scope_id = "00000000-0000-0000-0000-00000000f404"
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-002")

    response = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": "00000000-0000-0000-0000-00000000f499",
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-missing-source",
                "idempotencyKey": "idem-fin-alloc-missing-source",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 404
    assert response.json()["message"] == "Financial allocation source record not found."


def test_financial_allocation_list_denies_non_finance_roles() -> None:
    target_scope_id = "00000000-0000-0000-0000-00000000f405"
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-003")

    response = client.get(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "FORBIDDEN"
    assert response.json()["message"] == "Actor is not allowed to read financial allocations."


def test_financial_allocation_create_replays_idempotent_response() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f406"
    target_scope_id = "00000000-0000-0000-0000-00000000f407"
    cost_record_id = "00000000-0000-0000-0000-00000000f408"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-004")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-004")
    _seed_project_cost_record(cost_record_id, source_scope_id, amount=900000.0)

    payload = {
        "sourceRecordType": "cost_record",
        "sourceRecordId": cost_record_id,
        "allocationBasis": "manual_full",
        "meta": {
            "correlationId": "corr-fin-alloc-idem",
            "idempotencyKey": "idem-fin-alloc-idem",
            "actorId": "admin-1",
            "actorRole": "admin",
        },
    }

    first = client.post(f"/api/v1/projects/{target_scope_id}/financial-allocations", json=payload)
    second = client.post(f"/api/v1/projects/{target_scope_id}/financial-allocations", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json() == first.json()
    assert [event["eventName"] for event in memory.list_events()] == ["financial_allocation.recorded"]


def test_financial_allocation_create_rejects_duplicate_source_for_same_scope() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f409"
    target_scope_id = "00000000-0000-0000-0000-00000000f410"
    cost_record_id = "00000000-0000-0000-0000-00000000f411"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-005")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-005")
    _seed_project_cost_record(cost_record_id, source_scope_id)

    first = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-dup-1",
                "idempotencyKey": "idem-fin-alloc-dup-1",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-dup-2",
                "idempotencyKey": "idem-fin-alloc-dup-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["message"] == "Financial allocation already exists for this source record."


def test_financial_allocation_create_rejects_duplicate_source_across_scopes() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f415"
    first_target_scope_id = "00000000-0000-0000-0000-00000000f416"
    second_target_scope_id = "00000000-0000-0000-0000-00000000f417"
    cost_record_id = "00000000-0000-0000-0000-00000000f418"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-007")
    _seed_project_scope(first_target_scope_id, name="First Target", code="PRJ-TGT-007A")
    _seed_project_scope(second_target_scope_id, name="Second Target", code="PRJ-TGT-007B")
    _seed_project_cost_record(cost_record_id, source_scope_id)

    first = client.post(
        f"/api/v1/projects/{first_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-global-dup-1",
                "idempotencyKey": "idem-fin-alloc-global-dup-1",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second = client.post(
        f"/api/v1/projects/{second_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-global-dup-2",
                "idempotencyKey": "idem-fin-alloc-global-dup-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["message"] == "Financial allocation already exists for this source record."


def test_financial_allocation_create_rejects_cross_organization_source() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f412"
    target_scope_id = "00000000-0000-0000-0000-00000000f413"
    cost_record_id = "00000000-0000-0000-0000-00000000f414"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-006")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-006")
    target_scope = memory.get_project_scope(target_scope_id)
    assert target_scope is not None
    target_scope["organizationId"] = "org-2"
    memory.save_project_scope(target_scope_id, target_scope)
    _seed_project_cost_record(cost_record_id, source_scope_id, organization_id="org-1")

    response = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_full",
            "meta": {
                "correlationId": "corr-fin-alloc-cross-org",
                "idempotencyKey": "idem-fin-alloc-cross-org",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 409
    assert response.json()["message"] == "Financial allocation source record organization does not match the target project scope."


def test_financial_allocation_create_rejects_weighted_allocation_without_weight() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f419"
    target_scope_id = "00000000-0000-0000-0000-00000000f420"
    cost_record_id = "00000000-0000-0000-0000-00000000f421"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-008")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-008")
    _seed_project_cost_record(cost_record_id, source_scope_id)

    response = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "meta": {
                "correlationId": "corr-fin-alloc-weight-missing",
                "idempotencyKey": "idem-fin-alloc-weight-missing",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 422


def test_financial_allocation_create_weighted_allocation_calculates_amount() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f422"
    target_scope_id = "00000000-0000-0000-0000-00000000f423"
    cost_record_id = "00000000-0000-0000-0000-00000000f424"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-009")
    _seed_project_scope(target_scope_id, name="Target Scope", code="PRJ-TGT-009")
    _seed_project_cost_record(cost_record_id, source_scope_id, amount=1000.0)

    response = client.post(
        f"/api/v1/projects/{target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "allocationWeight": 0.6,
            "meta": {
                "correlationId": "corr-fin-alloc-weighted-create",
                "idempotencyKey": "idem-fin-alloc-weighted-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert response.status_code == 201
    payload = response.json()["data"]
    assert payload["allocationBasis"] == "manual_weighted"
    assert payload["allocationWeight"] == 0.6
    assert payload["allocatedAmount"] == 600.0


def test_financial_allocation_create_weighted_allocation_allows_second_scope_until_total_weight_reaches_one() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f425"
    first_target_scope_id = "00000000-0000-0000-0000-00000000f426"
    second_target_scope_id = "00000000-0000-0000-0000-00000000f427"
    cost_record_id = "00000000-0000-0000-0000-00000000f428"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-010")
    _seed_project_scope(first_target_scope_id, name="First Target", code="PRJ-TGT-010A")
    _seed_project_scope(second_target_scope_id, name="Second Target", code="PRJ-TGT-010B")
    _seed_project_cost_record(cost_record_id, source_scope_id, amount=1000.0)

    first = client.post(
        f"/api/v1/projects/{first_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "allocationWeight": 0.6,
            "meta": {
                "correlationId": "corr-fin-alloc-weighted-1",
                "idempotencyKey": "idem-fin-alloc-weighted-1",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second = client.post(
        f"/api/v1/projects/{second_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "allocationWeight": 0.4,
            "meta": {
                "correlationId": "corr-fin-alloc-weighted-2",
                "idempotencyKey": "idem-fin-alloc-weighted-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["data"]["allocatedAmount"] == 400.0


def test_financial_allocation_create_weighted_allocation_rejects_total_weight_above_one() -> None:
    source_scope_id = "00000000-0000-0000-0000-00000000f429"
    first_target_scope_id = "00000000-0000-0000-0000-00000000f430"
    second_target_scope_id = "00000000-0000-0000-0000-00000000f431"
    cost_record_id = "00000000-0000-0000-0000-00000000f432"
    _seed_project_scope(source_scope_id, name="Source Scope", code="PRJ-SRC-011")
    _seed_project_scope(first_target_scope_id, name="First Target", code="PRJ-TGT-011A")
    _seed_project_scope(second_target_scope_id, name="Second Target", code="PRJ-TGT-011B")
    _seed_project_cost_record(cost_record_id, source_scope_id, amount=1000.0)

    first = client.post(
        f"/api/v1/projects/{first_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "allocationWeight": 0.7,
            "meta": {
                "correlationId": "corr-fin-alloc-weighted-over-1",
                "idempotencyKey": "idem-fin-alloc-weighted-over-1",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    second = client.post(
        f"/api/v1/projects/{second_target_scope_id}/financial-allocations",
        json={
            "sourceRecordType": "cost_record",
            "sourceRecordId": cost_record_id,
            "allocationBasis": "manual_weighted",
            "allocationWeight": 0.5,
            "meta": {
                "correlationId": "corr-fin-alloc-weighted-over-2",
                "idempotencyKey": "idem-fin-alloc-weighted-over-2",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["message"] == "Financial allocation total weight exceeds 1.0 for this source record."