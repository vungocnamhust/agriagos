from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation, request_meta
from app.models.actor_authority import (
    ActorIdentityDetail,
    ActorIdentityResponse,
    CreateActorIdentityRequest,
)
from app.models.common import ErrorResponse
from app.services import actor_authority as svc

router = APIRouter()


ACTOR_AUTHORITY_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post("", response_model=ActorIdentityResponse, status_code=201, responses=ACTOR_AUTHORITY_ERROR_RESPONSES)
def create_actor_identity(request: Request, payload: CreateActorIdentityRequest) -> ActorIdentityResponse:
    return svc.create_actor_identity(apply_request_correlation(request, payload))


@router.get("/{actor_id}", response_model=ActorIdentityDetail, responses=ACTOR_AUTHORITY_ERROR_RESPONSES)
def get_actor_identity(actor_id: str, request: Request) -> ActorIdentityDetail:
    return svc.get_actor_identity_for_actor(actor_id, meta=request_meta(request))