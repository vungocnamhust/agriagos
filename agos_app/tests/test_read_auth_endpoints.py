from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.store import memory


client = TestClient(app)


def _auth_headers(
    *,
    actor_role: str,
    actor_id: str = "actor-1",
    delegated_actor_role: str | None = None,
    bypass_requested: bool = False,
) -> dict[str, str]:
    headers = {
        "X-Actor-Id": actor_id,
        "X-Actor-Role": actor_role,
    }
    if delegated_actor_role is not None:
        headers["X-Delegated-Actor-Role"] = delegated_actor_role
    if bypass_requested:
        headers["X-Bypass-Requested"] = "true"
    return headers


def test_events_query_requires_scope_for_viewer_and_audits_denial() -> None:
    response = client.get("/api/v1/events", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 403
    assert response.json()["message"] == "Event queries for this role must include at least one scoping filter."
    assert memory.list_audit_logs()[-1]["actionName"] == "event.query"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "event_scope_required"


def test_events_query_allows_scoped_viewer_access() -> None:
    memory.append_event(
        {
            "eventId": "evt-1",
            "eventName": "order.confirmed",
            "eventType": "OrderConfirmed",
            "eventVersion": 1,
            "aggregateType": "Order",
            "aggregateId": "order-1",
            "occurredAt": "2026-04-12T00:00:00Z",
            "actorType": "user",
            "actorId": "sales-1",
            "correlationId": "corr-evt-1",
            "causationId": None,
            "idempotencyKey": None,
            "source": "core",
            "tenantId": "default",
            "payload": {},
        }
    )

    response = client.get(
        "/api/v1/events",
        params={"aggregateType": "Order"},
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["eventName"] == "order.confirmed"


def test_events_query_allows_agent_with_delegated_viewer_role() -> None:
    memory.append_event(
        {
            "eventId": "evt-2",
            "eventName": "order.packed",
            "eventType": "OrderPacked",
            "eventVersion": 1,
            "aggregateType": "Order",
            "aggregateId": "order-2",
            "occurredAt": "2026-04-12T01:00:00Z",
            "actorType": "user",
            "actorId": "ops-1",
            "correlationId": "corr-evt-2",
            "causationId": None,
            "idempotencyKey": None,
            "source": "core",
            "tenantId": "default",
            "payload": {},
        }
    )

    response = client.get(
        "/api/v1/events",
        params={"aggregateType": "Order"},
        headers=_auth_headers(actor_role="agent", actor_id="agent-1", delegated_actor_role="viewer"),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["eventName"] == "order.packed"


def test_events_query_denies_sales_role() -> None:
    response = client.get(
        "/api/v1/events",
        params={"aggregateType": "Order"},
        headers=_auth_headers(actor_role="sales", actor_id="sales-1"),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Actor is not allowed to query the event stream."
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_event_query"


def test_events_query_denies_bypass_requests_and_audits() -> None:
    response = client.get(
        "/api/v1/events",
        params={"aggregateType": "Order"},
        headers=_auth_headers(actor_role="viewer", actor_id="viewer-1", bypass_requested=True),
    )

    assert response.status_code == 403
    assert response.json()["message"] == "Agent bypass lane is not enabled in Phase 1."
    assert memory.list_audit_logs()[-1]["actionName"] == "event.query"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "agent_execution_not_allowed"


def test_raw_farm_plots_deny_viewer_and_audit() -> None:
    response = client.get("/api/v1/farm/plots", headers=_auth_headers(actor_role="viewer", actor_id="viewer-1"))

    assert response.status_code == 403
    assert response.json()["message"] == "Actor is not allowed to list raw farm plots."
    assert memory.list_audit_logs()[-1]["actionName"] == "farm.plot.list"
    assert memory.list_audit_logs()[-1]["reasonCode"] == "forbidden_farm_plot_read"


def test_raw_farm_plots_allow_ops_and_return_organization_id() -> None:
    memory.save_plot(
        "plot-1",
        {
            "plotId": "plot-1",
            "plotCode": "PLOT-001",
            "organizationId": "org-1",
            "name": "Garden A",
            "locationText": "Da Lat",
            "areaValue": 2.0,
            "areaUnit": "ha",
            "status": "active",
        },
    )

    response = client.get("/api/v1/farm/plots", headers=_auth_headers(actor_role="ops", actor_id="ops-1"))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["plotId"] == "plot-1"
    assert response.json()[0]["organizationId"] == "org-1"
    assert response.json()[0]["assignments"] == []


def test_raw_farm_crop_cycles_allow_ops() -> None:
    memory.save_plot(
        "plot-1",
        {
            "plotId": "plot-1",
            "plotCode": "PLOT-001",
            "organizationId": "org-1",
            "name": "Garden A",
            "locationText": "Da Lat",
            "areaValue": 2.0,
            "areaUnit": "ha",
            "status": "active",
        },
    )
    memory.save_crop_cycle(
        "cycle-1",
        {
            "cropCycleId": "cycle-1",
            "plotId": "plot-1",
            "organizationId": "org-1",
            "cropName": "Strawberry",
            "growthStage": "maturing",
            "status": "active",
            "expectedHarvestFrom": "2026-05-01",
            "expectedHarvestTo": "2026-05-10",
        },
    )

    response = client.get("/api/v1/farm/crop-cycles", headers=_auth_headers(actor_role="ops", actor_id="ops-1"))

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["cropCycleId"] == "cycle-1"
    assert response.json()[0]["organizationId"] == "org-1"
    assert response.json()[0]["assignments"] == []


def test_raw_farm_surfaces_include_project_assignments() -> None:
    memory.save_plot(
        "plot-asg-1",
        {
            "plotId": "plot-asg-1",
            "plotCode": "PLOT-ASG-001",
            "organizationId": "org-1",
            "name": "Garden B",
            "locationText": "Da Lat",
            "areaValue": 3.0,
            "areaUnit": "ha",
            "status": "active",
        },
    )
    memory.save_crop_cycle(
        "cycle-asg-1",
        {
            "cropCycleId": "cycle-asg-1",
            "plotId": "plot-asg-1",
            "organizationId": "org-1",
            "cropName": "Coffee",
            "growthStage": "growing",
            "status": "active",
            "expectedHarvestFrom": "2026-06-01",
            "expectedHarvestTo": "2026-06-10",
        },
    )
    memory.save_project_assignment(
        "assignment-plot-1",
        {
            "projectAssignmentId": "assignment-plot-1",
            "projectScopeId": "00000000-0000-0000-0000-00000000a304",
            "targetType": "plot",
            "targetId": "plot-asg-1",
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": None,
            "endedReason": None,
            "metadata": {},
        },
    )
    memory.save_project_assignment(
        "assignment-cycle-1",
        {
            "projectAssignmentId": "assignment-cycle-1",
            "projectScopeId": "00000000-0000-0000-0000-00000000a305",
            "targetType": "crop_cycle",
            "targetId": "cycle-asg-1",
            "isPrimary": True,
            "attributionWeight": 1.0,
            "createdAt": memory.now_iso(),
            "endedAt": None,
            "endedReason": None,
            "metadata": {},
        },
    )

    plots_response = client.get("/api/v1/farm/plots", headers=_auth_headers(actor_role="ops", actor_id="ops-1"))
    crop_cycles_response = client.get("/api/v1/farm/crop-cycles", headers=_auth_headers(actor_role="ops", actor_id="ops-1"))

    assert plots_response.status_code == 200
    assert plots_response.json()[0]["assignments"][0]["targetType"] == "plot"
    assert crop_cycles_response.status_code == 200
    assert crop_cycles_response.json()[0]["assignments"][0]["targetType"] == "crop_cycle"
