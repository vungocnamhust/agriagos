from __future__ import annotations

from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.common import Meta
from app.models.project_cost_records import CreateProjectCostRecordRequest
from app.services import project_cost_records as cost_record_service
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
            "name": "Cost Scope",
            "projectScopeType": "value_stream",
            "status": "active",
            "seasonYear": "2026",
            "ownerActorId": "founder-1",
            "createdAt": memory.now_iso(),
            "updatedAt": memory.now_iso(),
        },
    )


def _seed_project_assignment(project_scope_id: str, assignment_id: str, target_id: str = "lot-1") -> None:
    memory.save_project_assignment(
        assignment_id,
        {
            "projectAssignmentId": assignment_id,
            "projectScopeId": project_scope_id,
            "targetType": "lot",
            "targetId": target_id,
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": None,
            "endedReason": None,
            "metadata": {},
        },
    )


def _record_confirmed_contribution(project_scope_id: str, assignment_id: str, contribution_id: str) -> None:
    memory.save_project_contribution(
        contribution_id,
        {
            "projectContributionEventId": contribution_id,
            "projectScopeId": project_scope_id,
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
            "status": "confirmed",
            "confirmedBy": "admin-1",
            "confirmedAt": memory.now_iso(),
            "rejectionReason": None,
            "source": "manual",
            "metadata": {},
            "createdAt": memory.now_iso(),
        },
    )


def test_project_cost_record_routes_record_and_list_costs() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000c401"
    assignment_id = "00000000-0000-0000-0000-00000000c402"
    contribution_id = "00000000-0000-0000-0000-00000000c403"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)
    _record_confirmed_contribution(project_scope_id, assignment_id, contribution_id)

    created = client.post(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        json={
            "costType": "labor_payout",
            "amount": 450000,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": contribution_id,
            "attributionPolicy": "direct_source_link",
            "meta": {
                "correlationId": "corr-project-cost-create",
                "idempotencyKey": "idem-project-cost-create",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )

    assert created.status_code == 201
    payload = created.json()["data"]
    assert payload["projectScopeId"] == project_scope_id
    assert payload["costType"] == "labor_payout"
    assert payload["sourceObjectId"] == contribution_id

    listed = client.get(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        headers=_auth_headers(actor_role="accountant", actor_id="acct-1"),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["costRecordId"] == payload["costRecordId"]


def test_project_cost_record_routes_reject_missing_or_unconfirmed_contribution_sources() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000c404"
    assignment_id = "00000000-0000-0000-0000-00000000c405"
    unconfirmed_contribution_id = "00000000-0000-0000-0000-00000000c406"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)
    memory.save_project_contribution(
        unconfirmed_contribution_id,
        {
            "projectContributionEventId": unconfirmed_contribution_id,
            "projectScopeId": project_scope_id,
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
            "status": "proposed",
            "confirmedBy": None,
            "confirmedAt": None,
            "rejectionReason": None,
            "source": "manual",
            "metadata": {},
            "createdAt": memory.now_iso(),
        },
    )

    missing = client.post(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        json={
            "costType": "labor_payout",
            "amount": 450000,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": "00000000-0000-0000-0000-00000000c499",
            "attributionPolicy": "direct_source_link",
            "meta": {
                "correlationId": "corr-project-cost-missing-source",
                "idempotencyKey": "idem-project-cost-missing-source",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert missing.status_code == 404

    unconfirmed = client.post(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        json={
            "costType": "labor_payout",
            "amount": 450000,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": unconfirmed_contribution_id,
            "attributionPolicy": "direct_source_link",
            "meta": {
                "correlationId": "corr-project-cost-unconfirmed-source",
                "idempotencyKey": "idem-project-cost-unconfirmed-source",
                "actorId": "admin-1",
                "actorRole": "admin",
            },
        },
    )
    assert unconfirmed.status_code == 422
    assert unconfirmed.json()["message"] == "Cost source contribution must be confirmed."
    audit = memory.list_audit_logs()[-1]
    assert audit["reasonCode"] == "project_cost_record_source_unconfirmed"
    assert audit["metadata"]["authorityBasis"] == "runtime_role"
    assert audit["metadata"]["effectiveActorRole"] == "admin"


def test_project_cost_record_service_validates_contribution_after_transaction_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000c407"
    contribution_id = "00000000-0000-0000-0000-00000000c408"
    transaction_entered = False

    @contextmanager
    def _fake_transaction():
        nonlocal transaction_entered
        transaction_entered = True
        yield

    def _get_scope_or_404(_: str) -> dict[str, str]:
        return {"organizationId": "org-1"}

    def _get_contribution_or_404(_: str) -> dict[str, str]:
        assert transaction_entered is True
        return {
            "projectScopeId": project_scope_id,
            "organizationId": "org-1",
            "status": "confirmed",
        }

    monkeypatch.setattr(cost_record_service, "postgres_enabled", lambda: True)
    monkeypatch.setattr(cost_record_service, "postgres_transaction", _fake_transaction)
    monkeypatch.setattr(cost_record_service, "_get_project_scope_record_or_404", _get_scope_or_404)
    monkeypatch.setattr(cost_record_service, "_get_project_contribution_record_or_404", _get_contribution_or_404)
    monkeypatch.setattr(cost_record_service.project_cost_record_store, "upsert_project_cost_record", lambda record: None)
    monkeypatch.setattr(cost_record_service.events, "emit", lambda **kwargs: {"eventName": kwargs["event_name"]})
    monkeypatch.setattr(cost_record_service, "append_audit_decision", lambda **kwargs: None)
    monkeypatch.setattr(cost_record_service, "check_idempotency", lambda key: None)
    monkeypatch.setattr(cost_record_service, "record_idempotency", lambda *args, **kwargs: None)

    response = cost_record_service.create_project_cost_record(
        project_scope_id,
        CreateProjectCostRecordRequest(
            costType="labor_payout",
            amount=450000,
            currency="VND",
            recognizedAt="2026-04-16T10:00:00Z",
            sourceObjectType="project_contribution_event",
            sourceObjectId=contribution_id,
            attributionPolicy="direct_source_link",
            meta=Meta(
                correlationId="corr-project-cost-ordering",
                idempotencyKey="idem-project-cost-ordering",
                actorId="admin-1",
                actorRole="admin",
            ),
        ),
    )

    assert transaction_entered is True
    assert response.data.projectScopeId == project_scope_id


def test_project_cost_record_audit_captures_authority_context_for_allow_and_deny() -> None:
    project_scope_id = "00000000-0000-0000-0000-00000000c409"
    assignment_id = "00000000-0000-0000-0000-00000000c410"
    contribution_id = "00000000-0000-0000-0000-00000000c411"
    _seed_project_scope(project_scope_id)
    _seed_project_assignment(project_scope_id, assignment_id)
    _record_confirmed_contribution(project_scope_id, assignment_id, contribution_id)

    allowed = client.post(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        json={
            "costType": "labor_payout",
            "amount": 450000,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": contribution_id,
            "attributionPolicy": "direct_source_link",
            "meta": {
                "correlationId": "corr-project-cost-audit-allow",
                "idempotencyKey": "idem-project-cost-audit-allow",
                "actorId": "admin-1",
                "actorRole": "admin",
                "delegatedActorId": "principal-1",
                "delegatedActorRole": "viewer",
            },
        },
    )

    assert allowed.status_code == 201
    allowed_audit = memory.list_audit_logs()[-1]
    assert allowed_audit["actionName"] == "project_cost_record.record"
    assert allowed_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert allowed_audit["metadata"]["effectiveActorRole"] == "admin"
    assert allowed_audit["metadata"]["delegatedActorId"] == "principal-1"
    assert allowed_audit["metadata"]["delegatedActorRole"] == "viewer"

    denied = client.post(
        f"/api/v1/projects/{project_scope_id}/cost-records",
        json={
            "costType": "labor_payout",
            "amount": 450000,
            "currency": "VND",
            "recognizedAt": "2026-04-16T10:00:00Z",
            "sourceObjectType": "project_contribution_event",
            "sourceObjectId": contribution_id,
            "attributionPolicy": "direct_source_link",
            "meta": {
                "correlationId": "corr-project-cost-audit-deny",
                "idempotencyKey": "idem-project-cost-audit-deny",
                "actorId": "sales-1",
                "actorRole": "sales",
                "delegatedActorId": "principal-2",
                "delegatedActorRole": "accountant",
            },
        },
    )

    assert denied.status_code == 403
    denied_audit = memory.list_audit_logs()[-1]
    assert denied_audit["reasonCode"] == "forbidden_project_cost_record_write"
    assert denied_audit["metadata"]["authorityBasis"] == "runtime_role"
    assert denied_audit["metadata"]["effectiveActorRole"] == "sales"
    assert denied_audit["metadata"]["delegatedActorId"] == "principal-2"
    assert denied_audit["metadata"]["delegatedActorRole"] == "accountant"