from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation
from app.models.common import ErrorResponse
from app.models.lots import (
    AddLotEvidenceRequest,
    AdjustLotQuantityRequest,
    BlockLotRequest,
    CreateHarvestedLotRequest,
    CreateProcessedLotRequest,
    CreateQCReviewRequest,
    LotDetail,
    LotEvidenceListResponse,
    LotEvidenceResponse,
    LotResponse,
    QCReviewListResponse,
    QCReviewResponse,
    ReleaseLotRequest,
    UnblockLotRequest,
)
from app.services import lots as svc

router = APIRouter()


LOT_ERROR_RESPONSES = {
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}

RELEASE_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Permission or approval required"},
    **LOT_ERROR_RESPONSES,
}


@router.post("", response_model=LotResponse, status_code=201, responses={422: LOT_ERROR_RESPONSES[422]})
def create_harvested_lot(request: Request, payload: CreateHarvestedLotRequest) -> LotResponse:
    return svc.create_harvested_lot(apply_request_correlation(request, payload))


@router.post("/processed", response_model=LotResponse, status_code=201, responses={422: LOT_ERROR_RESPONSES[422]})
def create_processed_lot(request: Request, payload: CreateProcessedLotRequest) -> LotResponse:
    return svc.create_processed_lot(apply_request_correlation(request, payload))


@router.get("/{lot_id}", response_model=LotDetail, responses=LOT_ERROR_RESPONSES)
def get_lot(lot_id: str) -> LotDetail:
    return svc.get_lot(lot_id)


@router.post("/{lot_id}/release", response_model=LotResponse, responses=RELEASE_ERROR_RESPONSES)
def release_lot(lot_id: str, request: Request, payload: ReleaseLotRequest) -> LotResponse:
    return svc.release_lot(lot_id, apply_request_correlation(request, payload))


@router.post("/{lot_id}/block", response_model=LotResponse, responses=LOT_ERROR_RESPONSES)
def block_lot(lot_id: str, request: Request, payload: BlockLotRequest) -> LotResponse:
    return svc.block_lot(lot_id, apply_request_correlation(request, payload))


@router.post("/{lot_id}/unblock", response_model=LotResponse, responses=LOT_ERROR_RESPONSES)
def unblock_lot(lot_id: str, request: Request, payload: UnblockLotRequest) -> LotResponse:
    return svc.unblock_lot(lot_id, apply_request_correlation(request, payload))


@router.post("/{lot_id}/adjust", response_model=LotResponse, responses=LOT_ERROR_RESPONSES)
def adjust_lot_quantity(lot_id: str, request: Request, payload: AdjustLotQuantityRequest) -> LotResponse:
    return svc.adjust_lot_quantity(lot_id, apply_request_correlation(request, payload))


@router.post("/{lot_id}/evidence", response_model=LotEvidenceResponse, status_code=201, responses=LOT_ERROR_RESPONSES)
def add_lot_evidence(lot_id: str, request: Request, payload: AddLotEvidenceRequest) -> LotEvidenceResponse:
    return svc.add_lot_evidence(lot_id, apply_request_correlation(request, payload))


@router.get("/{lot_id}/evidence", response_model=LotEvidenceListResponse, responses=LOT_ERROR_RESPONSES)
def get_lot_evidence(lot_id: str) -> LotEvidenceListResponse:
    return svc.get_lot_evidence(lot_id)


@router.post("/{lot_id}/qc-reviews", response_model=QCReviewResponse, status_code=201, responses=LOT_ERROR_RESPONSES)
def create_lot_qc_review(lot_id: str, request: Request, payload: CreateQCReviewRequest) -> QCReviewResponse:
    return svc.create_lot_qc_review(lot_id, apply_request_correlation(request, payload))


@router.get("/{lot_id}/qc-reviews", response_model=QCReviewListResponse, responses=LOT_ERROR_RESPONSES)
def get_lot_qc_reviews(lot_id: str) -> QCReviewListResponse:
    return svc.get_lot_qc_reviews(lot_id)
