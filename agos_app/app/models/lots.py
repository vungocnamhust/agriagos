from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from app.models.common import Meta
from app.models.enums import LotStatus


LotSourceType = Literal["crop_cycle", "processing_batch"]
HarvestedLotSourceType = Literal["crop_cycle"]
LotUnit = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"(?i)^kg$")]

class LotDetail(BaseModel):
    lotId: str
    lotCode: str
    productSkuId: str
    sourceType: LotSourceType
    sourceRefId: str
    harvestOrProductionDate: str
    actualQty: float
    releasedQty: float
    availableQty: float
    reservedQty: float
    unit: Literal["kg"] = "kg"  # (04-canonical-data-model.md — unit via inventory movement context)
    status: LotStatus  # (06-state-transitions.md)

class LotResponse(BaseModel):
    data: LotDetail

class CreateHarvestedLotRequest(BaseModel):
    productSkuId: str
    sourceType: HarvestedLotSourceType
    sourceRefId: str
    actualQty: float
    unit: LotUnit | None = None
    harvestOrProductionDate: str
    qualityNote: str | None = None
    attachments: list[str] = []
    requiresQc: bool = False
    meta: Meta | None = None

    @model_validator(mode="after")
    def validate_initial_status_flags(self) -> "CreateHarvestedLotRequest":
        if self.unit is not None:
            self.unit = self.unit.lower()
        return self


class CreateProcessedLotRequest(BaseModel):
    productSkuId: str
    processRefId: str
    actualQty: float
    unit: LotUnit | None = None
    harvestOrProductionDate: str
    qualityNote: str | None = None
    attachments: list[str] = []
    requiresQc: bool = False
    meta: Meta | None = None

    @model_validator(mode="after")
    def normalize_unit(self) -> "CreateProcessedLotRequest":
        if self.unit is not None:
            self.unit = self.unit.lower()
        return self


class AdjustLotQuantityRequest(BaseModel):
    newActualQty: float
    reason: str
    meta: Meta | None = None

class ReleaseLotRequest(BaseModel):
    releasedQty: float
    qualityStatus: str | None = None
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
