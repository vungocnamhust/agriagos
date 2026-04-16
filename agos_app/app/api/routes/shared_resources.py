from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation, request_meta
from app.models.common import ErrorResponse
from app.models.shared_resources import (
    CreateSharedResourceRequest,
    SharedResourceDetail,
    SharedResourceListResponse,
    SharedResourceResponse,
)
from app.services import shared_resources as svc


router = APIRouter()


SHARED_RESOURCE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post("", response_model=SharedResourceResponse, status_code=201, responses=SHARED_RESOURCE_ERROR_RESPONSES)
def create_shared_resource(request: Request, payload: CreateSharedResourceRequest) -> SharedResourceResponse:
    return svc.create_shared_resource(apply_request_correlation(request, payload))


@router.get("", response_model=SharedResourceListResponse, responses=SHARED_RESOURCE_ERROR_RESPONSES)
def list_shared_resources(request: Request) -> SharedResourceListResponse:
    return SharedResourceListResponse(items=svc.list_shared_resources_for_actor(meta=request_meta(request)))


@router.get("/{shared_resource_id}", response_model=SharedResourceDetail, responses=SHARED_RESOURCE_ERROR_RESPONSES)
def get_shared_resource(shared_resource_id: UUID, request: Request) -> SharedResourceDetail:
    return svc.get_shared_resource_for_actor(str(shared_resource_id), meta=request_meta(request))