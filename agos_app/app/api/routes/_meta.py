from __future__ import annotations

from typing import TypeVar

from fastapi import Request
from pydantic import BaseModel

from app.models.common import CommandMetaRequest, Meta

PayloadT = TypeVar("PayloadT", bound=BaseModel)

_REQUEST_STATE_TO_META_FIELDS = {
    "correlation_id": "correlationId",
    "causation_id": "causationId",
    "actor_id": "actorId",
    "actor_role": "actorRole",
    "idempotency_key": "idempotencyKey",
    "external_ref": "externalRef",
    "bypass_requested": "bypassRequested",
    "delegated_actor_id": "delegatedActorId",
    "delegated_actor_role": "delegatedActorRole",
}

_REQUEST_HEADER_TO_META_FIELDS = {
    "x-correlation-id": "correlationId",
    "x-causation-id": "causationId",
    "x-actor-id": "actorId",
    "x-actor-role": "actorRole",
    "x-idempotency-key": "idempotencyKey",
    "x-external-ref": "externalRef",
    "x-bypass-requested": "bypassRequested",
    "x-delegated-actor-id": "delegatedActorId",
    "x-delegated-actor-role": "delegatedActorRole",
}

_BOOLEAN_META_FIELDS = {"bypassRequested"}


def _parse_header_value(meta_field: str, raw_value: str) -> object:
    if meta_field in _BOOLEAN_META_FIELDS:
        return raw_value.strip().lower() in {"1", "true", "yes", "on"}
    return raw_value


def _request_meta_seed(request: Request) -> dict[str, object]:
    values: dict[str, object] = {}

    for state_field, meta_field in _REQUEST_STATE_TO_META_FIELDS.items():
        state_value = getattr(request.state, state_field, None)
        if state_value is not None:
            values[meta_field] = state_value

    for header_name, meta_field in _REQUEST_HEADER_TO_META_FIELDS.items():
        raw_value = request.headers.get(header_name)
        if raw_value is not None and meta_field not in values:
            values[meta_field] = _parse_header_value(meta_field, raw_value)

    return values


def request_meta(request: Request) -> Meta | None:
    values = _request_meta_seed(request)
    if not values:
        return None
    return Meta(**values)


def _meta_updates_from_request_state(request: Request, meta: Meta | None) -> dict[str, object]:
    updates: dict[str, object] = {}
    request_values = _request_meta_seed(request)

    for meta_field, request_value in request_values.items():
        if request_value is None:
            continue

        current_value = getattr(meta, meta_field, None) if meta is not None else None
        if current_value is None:
            updates[meta_field] = request_value

    return updates


def apply_request_correlation(request: Request, payload: PayloadT) -> PayloadT:
    if not hasattr(payload, "meta"):
        return payload

    meta = getattr(payload, "meta", None)
    updates = _meta_updates_from_request_state(request, meta)
    if not updates:
        return payload

    if meta is None:
        meta = Meta(**updates)
    else:
        meta = meta.model_copy(update=updates)

    return payload.model_copy(update={"meta": meta})


def ensure_command_payload(request: Request, payload: CommandMetaRequest | None) -> CommandMetaRequest:
    return apply_request_correlation(request, payload or CommandMetaRequest())