
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