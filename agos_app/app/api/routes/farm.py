from fastapi import APIRouter, Request

from app.api.routes._meta import request_meta
from app.models.common import ErrorResponse
from app.models.farm import CropCycleSummary, PlotSummary
from app.services import farm as svc

router = APIRouter()


@router.get("/plots", response_model=list[PlotSummary], responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def list_plots(request: Request) -> list[PlotSummary]:
    return [PlotSummary(**plot) for plot in svc.list_plots_for_actor(request_meta(request))]


@router.get("/crop-cycles", response_model=list[CropCycleSummary], responses={403: {"model": ErrorResponse, "description": "Forbidden"}})
def list_crop_cycles(request: Request, plotId: str | None = None, status: str | None = None) -> list[CropCycleSummary]:
    return [CropCycleSummary(**cycle) for cycle in svc.list_crop_cycles_for_actor(plotId, status, request_meta(request))]
