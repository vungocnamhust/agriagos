from fastapi import APIRouter, HTTPException
from app.models.lots import CreateHarvestedLotRequest, LotResponse, LotDetail, ReleaseLotRequest, BlockLotRequest

router = APIRouter()

@router.post("", response_model=LotResponse, status_code=201)
def create_harvested_lot(payload: CreateHarvestedLotRequest) -> LotResponse:
    # TODO: create lot in harvested/draft state, append HarvestedLotCreated event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/{lot_id}", response_model=LotDetail)
def get_lot(lot_id: str) -> LotDetail:
    # TODO: load lot detail
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{lot_id}/release", response_model=LotResponse)
def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    # TODO: validate QC/policy, update available qty, append LotReleased event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{lot_id}/block", response_model=LotResponse)
def block_lot(lot_id: str, payload: BlockLotRequest) -> LotResponse:
    # TODO: block lot and append LotBlocked event
    raise HTTPException(status_code=501, detail="Not implemented")
