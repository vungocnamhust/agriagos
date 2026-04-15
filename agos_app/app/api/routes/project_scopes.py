from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation, request_meta
from app.models.common import ErrorResponse
from app.models.project_assignments import (
    CreateProjectAssignmentRequest,
    EndProjectAssignmentRequest,
    ProjectAssignmentListResponse,
    ProjectAssignmentResponse,
)
from app.models.project_scopes import (
    ActivateProjectScopeRequest,
    ArchiveProjectScopeRequest,
    CloseProjectScopeRequest,
    CreateProjectScopeRequest,
    PauseProjectScopeRequest,
    ProjectScopeDetail,
    ProjectScopeListResponse,
    ProjectScopeResponse,
    UpdateProjectScopeRequest,
)
from app.services import project_scopes as svc
from app.services import project_assignments as assignment_svc

router = APIRouter()


PROJECT_SCOPE_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}


@router.post("", response_model=ProjectScopeResponse, status_code=201, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def create_project_scope(request: Request, payload: CreateProjectScopeRequest) -> ProjectScopeResponse:
    return svc.create_project_scope(apply_request_correlation(request, payload))


@router.get("", response_model=ProjectScopeListResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def list_project_scopes(request: Request) -> ProjectScopeListResponse:
    return ProjectScopeListResponse(items=svc.list_project_scopes_for_actor(meta=request_meta(request)))


@router.get("/{project_scope_id}", response_model=ProjectScopeDetail, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def get_project_scope(project_scope_id: UUID, request: Request) -> ProjectScopeDetail:
    return svc.get_project_scope_for_actor(str(project_scope_id), meta=request_meta(request))


@router.patch("/{project_scope_id}", response_model=ProjectScopeResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def update_project_scope(project_scope_id: UUID, request: Request, payload: UpdateProjectScopeRequest) -> ProjectScopeResponse:
    return svc.update_project_scope(str(project_scope_id), apply_request_correlation(request, payload))


@router.post("/{project_scope_id}/activate", response_model=ProjectScopeResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def activate_project_scope(project_scope_id: UUID, request: Request, payload: ActivateProjectScopeRequest) -> ProjectScopeResponse:
    return svc.activate_project_scope(str(project_scope_id), apply_request_correlation(request, payload))


@router.post("/{project_scope_id}/pause", response_model=ProjectScopeResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def pause_project_scope(project_scope_id: UUID, request: Request, payload: PauseProjectScopeRequest) -> ProjectScopeResponse:
    return svc.pause_project_scope(str(project_scope_id), apply_request_correlation(request, payload))


@router.post("/{project_scope_id}/close", response_model=ProjectScopeResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def close_project_scope(project_scope_id: UUID, request: Request, payload: CloseProjectScopeRequest) -> ProjectScopeResponse:
    return svc.close_project_scope(str(project_scope_id), apply_request_correlation(request, payload))


@router.post("/{project_scope_id}/archive", response_model=ProjectScopeResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def archive_project_scope(project_scope_id: UUID, request: Request, payload: ArchiveProjectScopeRequest) -> ProjectScopeResponse:
    return svc.archive_project_scope(str(project_scope_id), apply_request_correlation(request, payload))


@router.post("/{project_scope_id}/assignments", response_model=ProjectAssignmentResponse, status_code=201, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def create_project_assignment(
    project_scope_id: UUID,
    request: Request,
    payload: CreateProjectAssignmentRequest,
) -> ProjectAssignmentResponse:
    return assignment_svc.create_project_assignment(str(project_scope_id), apply_request_correlation(request, payload))


@router.get("/{project_scope_id}/assignments", response_model=ProjectAssignmentListResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def list_project_assignments(project_scope_id: UUID, request: Request) -> ProjectAssignmentListResponse:
    return ProjectAssignmentListResponse(
        items=assignment_svc.list_project_assignments_for_actor(str(project_scope_id), meta=request_meta(request))
    )


@router.post("/{project_scope_id}/assignments/{project_assignment_id}/end", response_model=ProjectAssignmentResponse, responses=PROJECT_SCOPE_ERROR_RESPONSES)
def end_project_assignment(
    project_scope_id: UUID,
    project_assignment_id: UUID,
    request: Request,
    payload: EndProjectAssignmentRequest,
) -> ProjectAssignmentResponse:
    return assignment_svc.end_project_assignment(
        str(project_scope_id),
        str(project_assignment_id),
        apply_request_correlation(request, payload),
    )