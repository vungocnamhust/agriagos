# pyright: reportMissingImports=false
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def test_customer_routes_support_search_patch_and_preference_detail() -> None:
    create_response = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Alice Nguyen",
            "phone": "0900000101",
            "province": "Lam Dong",
            "tags": ["vip"],
            "meta": {"correlationId": "corr-create-api", "idempotencyKey": "idem-create-api", "actorId": "sales-1", "actorRole": "sales"},
        },
    )

    assert create_response.status_code == 201
    customer = create_response.json()["data"]

    search_response = client.get("/api/v1/customers", params={"q": customer["customerCode"]})
    assert search_response.status_code == 200
    assert [item["customerId"] for item in search_response.json()["items"]] == [customer["customerId"]]

    patch_response = client.patch(
        f"/api/v1/customers/{customer['customerId']}",
        json={
            "notes": "Updated via API",
            "tags": ["vip", "priority"],
            "meta": {"correlationId": "corr-patch-api", "idempotencyKey": "idem-patch-api", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["notes"] == "Updated via API"
    assert patch_response.json()["tags"] == ["vip", "priority"]

    preference_response = client.post(
        f"/api/v1/customers/{customer['customerId']}/preferences",
        json={
            "preferenceType": "variety",
            "preferenceValue": "jasmine",
            "source": "human",
            "confidenceLevel": 1.0,
            "meta": {"correlationId": "corr-pref-api", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert preference_response.status_code == 200

    detail_response = client.get(f"/api/v1/customers/{customer['customerId']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["preferences"][0]["preferenceType"] == "variety"
    assert memory.list_events()[-1]["eventName"] == "customer.preference_updated"


def test_duplicate_candidate_routes_list_and_review() -> None:
    first = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Bao Tran",
            "phone": "0900000102",
            "province": "Lam Dong",
            "meta": {"correlationId": "corr-dup-first", "idempotencyKey": "idem-dup-first", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    second = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Bao Tran",
            "phone": "0900000103",
            "province": "Lam Dong",
            "meta": {"correlationId": "corr-dup-second", "idempotencyKey": "idem-dup-second", "actorId": "sales-1", "actorRole": "sales"},
        },
    )

    assert first.status_code == 201
    assert second.status_code == 201
    first_customer_id = first.json()["data"]["customerId"]

    all_candidates = client.get("/api/v1/customers/duplicate-candidates")
    assert all_candidates.status_code == 200
    assert len(all_candidates.json()["items"]) == 1
    candidate_id = all_candidates.json()["items"][0]["candidateId"]

    scoped_candidates = client.get(f"/api/v1/customers/{first_customer_id}/duplicate-candidates")
    assert scoped_candidates.status_code == 200
    assert scoped_candidates.json()["items"][0]["status"] == "open"

    review_response = client.post(
        f"/api/v1/customers/duplicate-candidates/{candidate_id}/review",
        json={
            "status": "reviewed_distinct",
            "note": "Different households",
            "meta": {"correlationId": "corr-dup-review", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "reviewed_distinct"
    assert review_response.json()["reviewedBy"] == "sales-1"


def test_customer_policy_routes_reject_forbidden_actions() -> None:
    created = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Alice Nguyen",
            "phone": "0900000199",
            "province": "Lam Dong",
            "meta": {"correlationId": "corr-policy-create", "idempotencyKey": "idem-policy-create", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert created.status_code == 201
    customer_id = created.json()["data"]["customerId"]

    forbidden_preference = client.post(
        f"/api/v1/customers/{customer_id}/preferences",
        json={
            "preferenceType": "variety",
            "preferenceValue": "jasmine",
            "source": "integration",
            "confidenceLevel": 0.9,
            "meta": {
                "correlationId": "corr-policy-pref-deny",
                "actorId": "sync-1",
                "actorRole": "integration",
            },
        },
    )
    assert forbidden_preference.status_code == 403
    assert forbidden_preference.json()["code"] == "FORBIDDEN"

    second = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Alice Nguyen",
            "phone": "0900000200",
            "province": "Lam Dong",
            "meta": {"correlationId": "corr-policy-second", "idempotencyKey": "idem-policy-second", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert second.status_code == 201

    candidates = client.get(f"/api/v1/customers/{customer_id}/duplicate-candidates")
    candidate_id = candidates.json()["items"][0]["candidateId"]
    forbidden_review = client.post(
        f"/api/v1/customers/duplicate-candidates/{candidate_id}/review",
        json={
            "status": "reviewed_distinct",
            "note": "Different households",
            "meta": {"correlationId": "corr-policy-review-deny", "actorId": "ops-1", "actorRole": "ops"},
        },
    )
    assert forbidden_review.status_code == 403
    assert forbidden_review.json()["code"] == "FORBIDDEN"


def test_customer_write_routes_reject_unauthorized_roles() -> None:
    forbidden_create = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Ops User",
            "phone": "0900000299",
            "meta": {"correlationId": "corr-create-forbidden", "idempotencyKey": "idem-create-forbidden", "actorId": "ops-1", "actorRole": "ops"},
        },
    )
    assert forbidden_create.status_code == 403
    assert forbidden_create.json()["code"] == "FORBIDDEN"

    created = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Allowed User",
            "phone": "0900000300",
            "meta": {"correlationId": "corr-create-allowed", "idempotencyKey": "idem-create-allowed", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert created.status_code == 201

    forbidden_update = client.patch(
        f"/api/v1/customers/{created.json()['data']['customerId']}",
        json={
            "notes": "ops should not update customer core",
            "meta": {"correlationId": "corr-update-forbidden", "idempotencyKey": "idem-update-forbidden", "actorId": "ops-1", "actorRole": "ops"},
        },
    )
    assert forbidden_update.status_code == 403
    assert forbidden_update.json()["code"] == "FORBIDDEN"


def test_customer_routes_return_conflict_and_validation_errors_for_core_rules() -> None:
    first = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Conflict User",
            "phone": "0900 000 201",
            "meta": {"correlationId": "corr-conflict-first", "idempotencyKey": "idem-conflict-first", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert first.status_code == 201

    duplicate = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Conflict User Duplicate",
            "phone": "+84 900000201",
            "meta": {"correlationId": "corr-conflict-second", "idempotencyKey": "idem-conflict-second", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "CONFLICT"

    preference = client.post(
        f"/api/v1/customers/{first.json()['data']['customerId']}/preferences",
        json={
            "preferenceType": "variety",
            "preferenceValue": "jasmine",
            "source": "ai_suggestion",
            "confidenceLevel": 0.7,
            "meta": {"correlationId": "corr-invalid-pref"},
        },
    )
    assert preference.status_code == 422
    assert preference.json()["code"] == "VALIDATION_ERROR"
    assert preference.json()["message"] == "Source is not allowed for canonical preference writes."


def test_customer_preference_route_allows_trusted_integration() -> None:
    created = client.post(
        "/api/v1/customers",
        json={
            "fullName": "Trusted Integration User",
            "phone": "0900000201",
            "meta": {"correlationId": "corr-trusted-create", "idempotencyKey": "idem-trusted-create", "actorId": "sales-1", "actorRole": "sales"},
        },
    )
    assert created.status_code == 201

    preference = client.post(
        f"/api/v1/customers/{created.json()['data']['customerId']}/preferences",
        json={
            "preferenceType": "variety",
            "preferenceValue": "jasmine",
            "source": "integration",
            "confidenceLevel": 0.9,
            "meta": {
                "correlationId": "corr-trusted-pref",
                "actorId": "trusted-sync",
                "actorRole": "integration",
                "externalRef": "crm:pref:trusted-1",
            },
        },
    )

    assert preference.status_code == 200
    assert preference.json()["source"] == "integration"
    assert preference.json()["confirmedBy"] == "trusted-sync"
