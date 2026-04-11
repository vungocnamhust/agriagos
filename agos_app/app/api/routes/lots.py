from fastapi import APIRouter

from app.models.lots import (
    AddLotEvidenceRequest,
    BlockLotRequest,
    CreateHarvestedLotRequest,
    CreateQCReviewRequest,
    LotDetail,
    LotEvidenceListResponse,
    LotEvidenceResponse,
    LotResponse,
    QCReviewListResponse,
    QCReviewResponse,
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


@router.post("/{lot_id}/evidence", response_model=LotEvidenceResponse, status_code=201)
def add_lot_evidence(lot_id: str, payload: AddLotEvidenceRequest) -> LotEvidenceResponse:
    return svc.add_lot_evidence(lot_id, payload)


@router.get("/{lot_id}/evidence", response_model=LotEvidenceListResponse)
def get_lot_evidence(lot_id: str) -> LotEvidenceListResponse:
    return svc.get_lot_evidence(lot_id)


@router.post("/{lot_id}/qc-reviews", response_model=QCReviewResponse, status_code=201)
def create_lot_qc_review(lot_id: str, payload: CreateQCReviewRequest) -> QCReviewResponse:
    return svc.create_lot_qc_review(lot_id, payload)


@router.get("/{lot_id}/qc-reviews", response_model=QCReviewListResponse)
def get_lot_qc_reviews(lot_id: str) -> QCReviewListResponse:
    return svc.get_lot_qc_reviews(lot_id)
