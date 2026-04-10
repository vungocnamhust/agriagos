from fastapi import APIRouter
from app.models.farm import PlotSummary, CropCycleSummary

router = APIRouter()

@router.get("/plots")
def list_plots() -> dict:
    # TODO: return canonical plot summaries or snapshots from farm system
    return {"items": []}

@router.get("/crop-cycles")
def list_crop_cycles(plotId: str | None = None, status: str | None = None) -> dict:
    # TODO: return crop cycle summaries
    return {"items": []}
