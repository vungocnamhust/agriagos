from __future__ import annotations

from typing import TypeVar

from fastapi import Request
from pydantic import BaseModel

from app.models.common import CommandMetaRequest, Meta

PayloadT = TypeVar("PayloadT", bound=BaseModel)


def apply_request_correlation(request: Request, payload: PayloadT) -> PayloadT:
    correlation_id = getattr(request.state, "correlation_id", None)
    if correlation_id is None or not hasattr(payload, "meta"):
        return payload

    meta = getattr(payload, "meta", None)
    if meta is None:
        meta = Meta(correlationId=correlation_id)
    elif meta.correlationId is None:
        meta = meta.model_copy(update={"correlationId": correlation_id})
    else:
        return payload

    return payload.model_copy(update={"meta": meta})


def ensure_command_payload(request: Request, payload: CommandMetaRequest | None) -> CommandMetaRequest:
    return apply_request_correlation(request, payload or CommandMetaRequest())