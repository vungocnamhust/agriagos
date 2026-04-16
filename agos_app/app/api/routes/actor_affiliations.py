from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation
from app.models.actor_authority import ActorAffiliationResponse, CreateActorAffiliationRequest
from app.models.common import ErrorResponse
from app.services import actor_authority as svc

router = APIRouter()


ACTOR_AFFILIATION_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post("", response_model=ActorAffiliationResponse, status_code=201, responses=ACTOR_AFFILIATION_ERROR_RESPONSES)
def create_actor_affiliation(request: Request, payload: CreateActorAffiliationRequest) -> ActorAffiliationResponse:
    return svc.create_actor_affiliation(apply_request_correlation(request, payload))