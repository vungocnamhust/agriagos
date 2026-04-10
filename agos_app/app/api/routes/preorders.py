from fastapi import APIRouter

from app.models.preorders import (
    AdjustPreorderRequest,
    CreatePreorderRequest,
    PreorderDetail,
    PreorderResponse,
)
from app.services import preorders as svc

router = APIRouter()


@router.post("", response_model=PreorderResponse, status_code=201)
def create_preorder(payload: CreatePreorderRequest) -> PreorderResponse:
    return svc.create_preorder(payload)


@router.get("/{preorder_id}", response_model=PreorderDetail)
def get_preorder(preorder_id: str) -> PreorderDetail:
    return svc.get_preorder(preorder_id)


@router.post("/{preorder_id}/adjust", response_model=PreorderResponse)
def adjust_preorder(preorder_id: str, payload: AdjustPreorderRequest) -> PreorderResponse:
    return svc.adjust_preorder(preorder_id, payload)
