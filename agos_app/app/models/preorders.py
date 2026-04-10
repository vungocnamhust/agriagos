from pydantic import BaseModel
from app.models.common import Meta

class PreorderDetail(BaseModel):
    preorderId: str
    preorderCode: str
    customerId: str
    productSkuId: str
    committedQty: float
    allocatedQty: float
    deliveredQty: float
    remainingQty: float
    status: str

class CreatePreorderRequest(BaseModel):
    customerId: str
    productSkuId: str
    committedQty: float
    deliveryCadence: str | None = None
    depositAmount: float | None = None
    notes: str | None = None
    meta: Meta | None = None

class AdjustPreorderRequest(BaseModel):
    newCommittedQty: float
    reason: str
    meta: Meta | None = None

class PreorderResponse(BaseModel):
    data: PreorderDetail
