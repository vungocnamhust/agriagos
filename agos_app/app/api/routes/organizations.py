from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation, request_meta
from app.models.common import ErrorResponse
from app.models.organizations import (
    ActivateOrganizationRequest,
    CloseOrganizationRequest,
    CreateOrganizationRequest,
    OrganizationDetail,
    OrganizationListResponse,
    OrganizationResponse,
    PauseOrganizationRequest,
    UpdateOrganizationRequest,
)
from app.services import organizations as svc

router = APIRouter()


ORGANIZATION_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post("", response_model=OrganizationResponse, status_code=201, responses=ORGANIZATION_ERROR_RESPONSES)
def create_organization(request: Request, payload: CreateOrganizationRequest) -> OrganizationResponse:
    return svc.create_organization(apply_request_correlation(request, payload))


@router.get("", response_model=OrganizationListResponse, responses=ORGANIZATION_ERROR_RESPONSES)
def list_organizations(request: Request) -> OrganizationListResponse:
    return OrganizationListResponse(items=svc.list_organizations_for_actor(meta=request_meta(request)))


@router.get("/{organization_id}", response_model=OrganizationDetail, responses=ORGANIZATION_ERROR_RESPONSES)
def get_organization(organization_id: UUID, request: Request) -> OrganizationDetail:
    return svc.get_organization_for_actor(str(organization_id), meta=request_meta(request))


@router.patch("/{organization_id}", response_model=OrganizationResponse, responses=ORGANIZATION_ERROR_RESPONSES)
def update_organization(organization_id: UUID, request: Request, payload: UpdateOrganizationRequest) -> OrganizationResponse:
    return svc.update_organization(str(organization_id), apply_request_correlation(request, payload))


@router.post("/{organization_id}/activate", response_model=OrganizationResponse, responses=ORGANIZATION_ERROR_RESPONSES)
def activate_organization(organization_id: UUID, request: Request, payload: ActivateOrganizationRequest) -> OrganizationResponse:
    return svc.activate_organization(str(organization_id), apply_request_correlation(request, payload))


@router.post("/{organization_id}/pause", response_model=OrganizationResponse, responses=ORGANIZATION_ERROR_RESPONSES)
def pause_organization(organization_id: UUID, request: Request, payload: PauseOrganizationRequest) -> OrganizationResponse:
    return svc.pause_organization(str(organization_id), apply_request_correlation(request, payload))


@router.post("/{organization_id}/close", response_model=OrganizationResponse, responses=ORGANIZATION_ERROR_RESPONSES)
def close_organization(organization_id: UUID, request: Request, payload: CloseOrganizationRequest) -> OrganizationResponse:
    return svc.close_organization(str(organization_id), apply_request_correlation(request, payload))