from fastapi import APIRouter

from app.services import farm as svc

router = APIRouter()


@router.get("/plots")
def list_plots() -> dict:
    return {"items": svc.list_plots()}


@router.get("/crop-cycles")
def list_crop_cycles(plotId: str | None = None, status: str | None = None) -> dict:
    return {"items": svc.list_crop_cycles(plotId, status)}
