from pydantic import BaseModel
from app.models.common import Meta
from app.models.enums import PreorderStatus

class PreorderDetail(BaseModel):
    preorderId: str
    preorderCode: str
    customerId: str
    productSkuId: str
    committedQty: float
    allocatedQty: float
    deliveredQty: float
    remainingQty: float
    cancelledQty: float = 0
    status: PreorderStatus  # required: draft|confirmed|active|completed|cancelled (06-state-transitions.md)
    startDate: str | None = None

class CreatePreorderRequest(BaseModel):
    customerId: str
    productSkuId: str
    committedQty: float
    startDate: str | None = None
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
