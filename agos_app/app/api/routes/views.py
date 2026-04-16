from fastapi import APIRouter, Request

from app.api.routes._meta import request_meta
from app.models.common import ErrorResponse
from app.models.farm import FarmView
from app.models.views import (
    AvailableLotListResponse,
    Customer360View,
    FarmSummaryBoardResponse,
    PendingFulfillmentListResponse,
    ProjectContributionSummaryResponse,
)
from app.services import views as svc

router = APIRouter()


@router.get(
    "/customer-360/{customer_id}",
    response_model=Customer360View,
    responses={403: {"model": ErrorResponse, "description": "Forbidden"}, 404: {"model": ErrorResponse, "description": "Customer Not Found"}},
)
def get_customer_360(request: Request, customer_id: str) -> Customer360View:
    return svc.get_customer_360_for_actor(customer_id, request_meta(request))


@router.get("/available-lots", response_model=AvailableLotListResponse, responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def get_available_lots_board(request: Request, skuId: str | None = None) -> AvailableLotListResponse:
    return svc.get_available_lots_board_for_actor(skuId, request_meta(request))


@router.get("/pending-fulfillment", response_model=PendingFulfillmentListResponse, responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def get_pending_fulfillment(request: Request) -> PendingFulfillmentListResponse:
    return svc.get_pending_fulfillment_for_actor(request_meta(request))


@router.get("/farm", response_model=FarmView, responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def get_farm_view(request: Request) -> FarmView:
    return svc.get_farm_view_for_actor(request_meta(request))


@router.get("/farm-summary-board", response_model=FarmSummaryBoardResponse, responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def get_farm_summary_board(request: Request) -> FarmSummaryBoardResponse:
    return svc.get_farm_summary_board_for_actor(request_meta(request))


@router.get(
    "/project-contribution-summary",
    response_model=ProjectContributionSummaryResponse,
    responses={403: {"model": ErrorResponse, "description": "Forbidden"}},
)
def get_project_contribution_summary(request: Request, projectScopeId: str | None = None) -> ProjectContributionSummaryResponse:
    return svc.get_project_contribution_summary_for_actor(projectScopeId, request_meta(request))
