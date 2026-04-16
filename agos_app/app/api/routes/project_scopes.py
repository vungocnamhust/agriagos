from __future__ import annotations

from typing import Any
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
from app.models.project_contributions import (
    ConfirmProjectContributionRequest,
    ProjectContributionListResponse,
    ProjectContributionResponse,
    RecordProjectContributionRequest,
    RejectProjectContributionRequest,
)
from app.models.project_cost_records import (
    CreateProjectCostRecordRequest,
    ProjectCostRecordListResponse,
    ProjectCostRecordResponse,
)
from app.models.project_revenue_records import (
    CreateProjectRevenueRecordRequest,
    ProjectRevenueRecordListResponse,
    ProjectRevenueRecordResponse,
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
from app.services import project_contributions as contribution_svc
from app.services import project_cost_records as cost_record_svc
from app.services import project_revenue_records as revenue_record_svc

router = APIRouter()


PROJECT_SCOPE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
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


@router.post(
    "/{project_scope_id}/contributions",
    response_model=ProjectContributionResponse,
    status_code=201,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def record_project_contribution(
    project_scope_id: UUID,
    request: Request,
    payload: RecordProjectContributionRequest,
) -> ProjectContributionResponse:
    return contribution_svc.record_project_contribution(str(project_scope_id), apply_request_correlation(request, payload))


@router.get(
    "/{project_scope_id}/contributions",
    response_model=ProjectContributionListResponse,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def list_project_contributions(project_scope_id: UUID, request: Request) -> ProjectContributionListResponse:
    return ProjectContributionListResponse(
        items=contribution_svc.list_project_contributions_for_actor(str(project_scope_id), meta=request_meta(request))
    )


@router.post(
    "/{project_scope_id}/contributions/{project_contribution_event_id}/confirm",
    response_model=ProjectContributionResponse,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def confirm_project_contribution(
    project_scope_id: UUID,
    project_contribution_event_id: UUID,
    request: Request,
    payload: ConfirmProjectContributionRequest,
) -> ProjectContributionResponse:
    return contribution_svc.confirm_project_contribution(
        str(project_scope_id),
        str(project_contribution_event_id),
        apply_request_correlation(request, payload),
    )


@router.post(
    "/{project_scope_id}/contributions/{project_contribution_event_id}/reject",
    response_model=ProjectContributionResponse,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def reject_project_contribution(
    project_scope_id: UUID,
    project_contribution_event_id: UUID,
    request: Request,
    payload: RejectProjectContributionRequest,
) -> ProjectContributionResponse:
    return contribution_svc.reject_project_contribution(
        str(project_scope_id),
        str(project_contribution_event_id),
        apply_request_correlation(request, payload),
    )


@router.post(
    "/{project_scope_id}/cost-records",
    response_model=ProjectCostRecordResponse,
    status_code=201,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def create_project_cost_record(
    project_scope_id: UUID,
    request: Request,
    payload: CreateProjectCostRecordRequest,
) -> ProjectCostRecordResponse:
    return cost_record_svc.create_project_cost_record(str(project_scope_id), apply_request_correlation(request, payload))


@router.get(
    "/{project_scope_id}/cost-records",
    response_model=ProjectCostRecordListResponse,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def list_project_cost_records(project_scope_id: UUID, request: Request) -> ProjectCostRecordListResponse:
    return ProjectCostRecordListResponse(
        items=cost_record_svc.list_project_cost_records_for_actor(str(project_scope_id), meta=request_meta(request))
    )


@router.post(
    "/{project_scope_id}/revenue-records",
    response_model=ProjectRevenueRecordResponse,
    status_code=201,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def create_project_revenue_record(
    project_scope_id: UUID,
    request: Request,
    payload: CreateProjectRevenueRecordRequest,
) -> ProjectRevenueRecordResponse:
    return revenue_record_svc.create_project_revenue_record(
        str(project_scope_id),
        apply_request_correlation(request, payload),
    )


@router.get(
    "/{project_scope_id}/revenue-records",
    response_model=ProjectRevenueRecordListResponse,
    responses=PROJECT_SCOPE_ERROR_RESPONSES,
)
def list_project_revenue_records(project_scope_id: UUID, request: Request) -> ProjectRevenueRecordListResponse:
    return ProjectRevenueRecordListResponse(
        items=revenue_record_svc.list_project_revenue_records_for_actor(
            str(project_scope_id),
            meta=request_meta(request),
        )
    )