from fastapi import APIRouter

from app.models.lots import (
    BlockLotRequest,
    CreateHarvestedLotRequest,
    LotDetail,
    LotResponse,
    ReleaseLotRequest,
)
from app.services import lots as svc

router = APIRouter()


@router.post("", response_model=LotResponse, status_code=201)
def create_harvested_lot(payload: CreateHarvestedLotRequest) -> LotResponse:
    return svc.create_harvested_lot(payload)


@router.get("/{lot_id}", response_model=LotDetail)
def get_lot(lot_id: str) -> LotDetail:
    return svc.get_lot(lot_id)


@router.post("/{lot_id}/release", response_model=LotResponse)
def release_lot(lot_id: str, payload: ReleaseLotRequest) -> LotResponse:
    return svc.release_lot(lot_id, payload)


@router.post("/{lot_id}/block", response_model=LotResponse)
def block_lot(lot_id: str, payload: BlockLotRequest) -> LotResponse:
    return svc.block_lot(lot_id, payload)
