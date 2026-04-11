from fastapi import APIRouter

from app.models.farm import CropCycleSummary, PlotSummary
from app.services import farm as svc

router = APIRouter()


@router.get("/plots", response_model=list[PlotSummary])
def list_plots() -> list[PlotSummary]:
    return svc.list_plots()


@router.get("/crop-cycles", response_model=list[CropCycleSummary])
def list_crop_cycles(plotId: str | None = None, status: str | None = None) -> list[CropCycleSummary]:
    return svc.list_crop_cycles(plotId, status)
