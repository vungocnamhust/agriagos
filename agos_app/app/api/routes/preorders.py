from fastapi import APIRouter, Request

from app.api.routes._meta import apply_request_correlation
from app.models.preorders import (
    ActivatePreorderRequest,
    AdjustPreorderRequest,
    CancelPreorderRequest,
    ConfirmPreorderRequest,
    CreatePreorderRequest,
    PreorderDetail,
    PreorderResponse,
)
from app.services import preorders as svc

router = APIRouter()


@router.post("", response_model=PreorderResponse, status_code=201)
def create_preorder(request: Request, payload: CreatePreorderRequest) -> PreorderResponse:
    return svc.create_preorder(apply_request_correlation(request, payload))


@router.get("/{preorder_id}", response_model=PreorderDetail)
def get_preorder(preorder_id: str) -> PreorderDetail:
    return svc.get_preorder(preorder_id)


@router.post("/{preorder_id}/adjust", response_model=PreorderResponse)
def adjust_preorder(preorder_id: str, request: Request, payload: AdjustPreorderRequest) -> PreorderResponse:
    return svc.adjust_preorder(preorder_id, apply_request_correlation(request, payload))


@router.post("/{preorder_id}/confirm", response_model=PreorderResponse)
def confirm_preorder(preorder_id: str, request: Request, payload: ConfirmPreorderRequest) -> PreorderResponse:
    return svc.confirm_preorder(preorder_id, apply_request_correlation(request, payload))


@router.post("/{preorder_id}/activate", response_model=PreorderResponse)
def activate_preorder(preorder_id: str, request: Request, payload: ActivatePreorderRequest) -> PreorderResponse:
    return svc.activate_preorder(preorder_id, apply_request_correlation(request, payload))


@router.post("/{preorder_id}/cancel", response_model=PreorderResponse)
def cancel_preorder(preorder_id: str, request: Request, payload: CancelPreorderRequest) -> PreorderResponse:
    return svc.cancel_preorder(preorder_id, apply_request_correlation(request, payload))
