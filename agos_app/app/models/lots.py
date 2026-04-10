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
