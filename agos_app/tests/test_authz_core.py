from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.core.authz import build_auth_context, ensure_bypass_permitted, normalize_actor_role
from app.core.write_context import meta_context
from app.models.common import Meta
from app.models.enums import ActorRole
from app.store import memory


@pytest.mark.parametrize(
    ("actor_role", "expected"),
    [
        ("admin_van_hanh", "admin"),
        ("ops_manager", "ops"),
        ("viewer/analyst", "viewer"),
        ("QC Reviewer", "qc_reviewer"),
    ],
)
def test_normalize_actor_role_maps_phase1_aliases(actor_role: str, expected: str) -> None:
    assert normalize_actor_role(actor_role) == expected


def test_normalize_actor_role_accepts_actor_role_enum() -> None:
    assert normalize_actor_role(ActorRole.accountant) == "accountant"


def test_build_auth_context_keeps_raw_and_normalized_roles() -> None:
    context = build_auth_context(
        Meta(
            correlationId="corr-authz",
            actorId="ops-1",
            actorRole="ops_manager",
            bypassRequested=True,
            delegatedActorRole="sales",
        )
    )

    assert context.actor_role == "ops_manager"
    assert context.normalized_actor_role == "ops"
    assert context.bypass_requested is True
    assert context.delegated_actor_role == "sales"


def test_meta_context_exposes_authz_fields_for_existing_services() -> None:
    context = meta_context(
        Meta(
            correlationId="corr-write-context",
            actorId="qc-1",
            actorRole="QC Reviewer",
            bypassRequested=False,
        )
    )

    assert context["actor_role"] == "QC Reviewer"
    assert context["normalized_actor_role"] == "qc_reviewer"
    assert context["bypass_requested"] is False


def test_disabled_bypass_request_is_denied_and_audited() -> None:
    context = build_auth_context(
        Meta(
            correlationId="corr-bypass",
            actorId="agent-1",
            actorRole="agent",
            bypassRequested=True,
            delegatedActorId="ops-1",
            delegatedActorRole="ops",
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        ensure_bypass_permitted(
            action_name="order.allocate",
            target_type="Order",
            target_id="order-1",
            context=context,
        )

    assert exc_info.value.status_code == 403
    audit_entry = memory.list_audit_logs()[-1]

    assert audit_entry["actorId"] == "agent-1"
    assert audit_entry["actorRole"] == "agent"
    assert audit_entry["actionName"] == "order.allocate"
    assert audit_entry["targetType"] == "Order"
    assert audit_entry["targetId"] == "order-1"
    assert audit_entry["decision"] == "denied"
    assert audit_entry["reasonCode"] == "agent_execution_not_allowed"
    assert audit_entry["correlationId"] == "corr-bypass"
    assert audit_entry["metadata"]["bypassRequested"] is True
    assert audit_entry["metadata"]["delegatedActorId"] == "ops-1"
    assert audit_entry["metadata"]["delegatedActorRole"] == "ops"