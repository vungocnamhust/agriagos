from pydantic import BaseModel
from app.models.common import Meta
from app.models.enums import LotStatus

class LotDetail(BaseModel):
    lotId: str
    lotCode: str
    productSkuId: str
    sourceType: str
    sourceRefId: str
    harvestOrProductionDate: str
    actualQty: float
    releasedQty: float
    availableQty: float
    reservedQty: float
    unit: str = "kg"  # (04-canonical-data-model.md — unit via inventory movement context)
    status: LotStatus  # (06-state-transitions.md)

class LotResponse(BaseModel):
    data: LotDetail

class CreateHarvestedLotRequest(BaseModel):
    productSkuId: str
    sourceType: str
    sourceRefId: str
    actualQty: float
    harvestOrProductionDate: str
    qualityNote: str | None = None
    attachments: list[str] = []
    meta: Meta | None = None

class ReleaseLotRequest(BaseModel):
    releasedQty: float
    qualityStatus: str | None = None
    note: str | None = None
    meta: Meta | None = None

class BlockLotRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class AddLotEvidenceRequest(BaseModel):
    evidenceType: str
    objectStorageKey: str | None = None
    textValue: str | None = None
    meta: Meta | None = None


class LotEvidenceItem(BaseModel):
    lotEvidenceId: str
    lotId: str
    evidenceType: str
    objectStorageKey: str | None = None
    textValue: str | None = None
    capturedAt: str
    actorId: str | None = None
    status: str


class LotEvidenceResponse(BaseModel):
    data: LotEvidenceItem


class LotEvidenceListResponse(BaseModel):
    items: list[LotEvidenceItem]


class CreateQCReviewRequest(BaseModel):
    checklistVersion: str
    result: str
    notes: str | None = None
    meta: Meta | None = None


class QCReviewItem(BaseModel):
    qcReviewId: str
    lotId: str
    checklistVersion: str
    result: str
    reviewerId: str | None = None
    reviewedAt: str
    notes: str | None = None


class QCReviewResponse(BaseModel):
    data: QCReviewItem


class QCReviewListResponse(BaseModel):
    items: list[QCReviewItem]
