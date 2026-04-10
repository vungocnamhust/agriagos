from fastapi import APIRouter, HTTPException
from app.models.preorders import CreatePreorderRequest, PreorderResponse, AdjustPreorderRequest, PreorderDetail

router = APIRouter()

@router.post("", response_model=PreorderResponse, status_code=201)
def create_preorder(payload: CreatePreorderRequest) -> PreorderResponse:
    # TODO: create preorder, set remaining_qty, append PreorderPlaced event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("/{preorder_id}", response_model=PreorderDetail)
def get_preorder(preorder_id: str) -> PreorderDetail:
    # TODO: load preorder detail
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{preorder_id}/adjust", response_model=PreorderResponse)
def adjust_preorder(preorder_id: str, payload: AdjustPreorderRequest) -> PreorderResponse:
    # TODO: validate state, adjust committed qty, append PreorderAdjusted event
    raise HTTPException(status_code=501, detail="Not implemented")
