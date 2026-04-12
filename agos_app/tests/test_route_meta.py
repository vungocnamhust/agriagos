from __future__ import annotations

from fastapi import Request
from pydantic import BaseModel

from app.api.routes._meta import apply_request_correlation, ensure_command_payload, request_meta
from app.models.common import Meta


class SamplePayload(BaseModel):
    value: str
    meta: Meta | None = None


def _build_request(**state_fields: object) -> Request:
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/test",
            "headers": [],
        }
    )
    for field_name, field_value in state_fields.items():
        setattr(request.state, field_name, field_value)
    return request


def test_apply_request_correlation_builds_meta_from_request_state() -> None:
    request = _build_request(
        correlation_id="corr-route-meta",
        actor_id="sales-1",
        actor_role="sales",
        bypass_requested=True,
        delegated_actor_role="ops",
    )

    payload = apply_request_correlation(request, SamplePayload(value="hello"))

    assert payload.meta is not None
    assert payload.meta.correlationId == "corr-route-meta"
    assert payload.meta.actorId == "sales-1"
    assert payload.meta.actorRole == "sales"
    assert payload.meta.bypassRequested is True
    assert payload.meta.delegatedActorRole == "ops"


def test_apply_request_correlation_only_fills_missing_meta_fields() -> None:
    request = _build_request(
        correlation_id="corr-from-state",
        actor_id="state-actor",
        actor_role="ops",
        delegated_actor_role="sales",
    )

    payload = apply_request_correlation(
        request,
        SamplePayload(
            value="hello",
            meta=Meta(
                correlationId="corr-from-payload",
                actorId="payload-actor",
                actorRole="QC Reviewer",
            ),
        ),
    )

    assert payload.meta is not None
    assert payload.meta.correlationId == "corr-from-payload"
    assert payload.meta.actorId == "payload-actor"
    assert payload.meta.actorRole == "QC Reviewer"
    assert payload.meta.delegatedActorRole == "sales"


def test_ensure_command_payload_adopts_auth_context_for_empty_commands() -> None:
    request = _build_request(
        correlation_id="corr-empty-command",
        actor_id="agent-1",
        actor_role="agent",
        bypass_requested=True,
        delegated_actor_id="ops-1",
        delegated_actor_role="ops",
    )

    payload = ensure_command_payload(request, None)

    assert payload.meta is not None
    assert payload.meta.correlationId == "corr-empty-command"
    assert payload.meta.actorId == "agent-1"
    assert payload.meta.actorRole == "agent"
    assert payload.meta.bypassRequested is True
    assert payload.meta.delegatedActorId == "ops-1"
    assert payload.meta.delegatedActorRole == "ops"


def test_request_meta_reads_headers_and_preserves_state_precedence() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/test",
            "headers": [
                (b"x-actor-id", b"header-actor"),
                (b"x-actor-role", b"viewer"),
                (b"x-bypass-requested", b" YeS "),
            ],
        }
    )
    request.state.actor_role = "sales"

    meta = request_meta(request)

    assert meta is not None
    assert meta.actorId == "header-actor"
    assert meta.actorRole == "sales"
    assert meta.bypassRequested is True