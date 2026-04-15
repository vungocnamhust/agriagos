from pydantic import BaseModel, Field
from app.models.common import Meta
from app.models.enums import PreorderStatus


class PreorderAdjustmentEntry(BaseModel):
    oldCommittedQty: float
    newCommittedQty: float
    reason: str
    changedAt: str
    actorId: str | None = None

class PreorderDetail(BaseModel):
    preorderId: str
    preorderCode: str
    organizationId: str | None = None
    customerId: str
    productSkuId: str
    committedQty: float
    allocatedQty: float
    deliveredQty: float
    remainingQty: float
    cancelledQty: float = 0
    status: PreorderStatus  # required: draft|confirmed|active|completed|cancelled (06-state-transitions.md)
    startDate: str | None = None
    version: int = 1
    adjustmentHistory: list[PreorderAdjustmentEntry] = Field(default_factory=list)

class CreatePreorderRequest(BaseModel):
    organizationId: str | None = None
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


class ConfirmPreorderRequest(BaseModel):
    meta: Meta | None = None


class ActivatePreorderRequest(BaseModel):
    meta: Meta | None = None


class CancelPreorderRequest(BaseModel):
    reason: str
    meta: Meta | None = None

class PreorderResponse(BaseModel):
    data: PreorderDetail
