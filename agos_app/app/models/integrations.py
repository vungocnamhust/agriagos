"""
Integration contract models.
Source of truth for cross-system mapping and inventory movement records.
See: 08-integration-contracts.md, 04-canonical-data-model.md
"""
from pydantic import BaseModel

from app.models.enums import SyncStatus


class ExternalMappingRecord(BaseModel):
    """
    Maps any Agri OS Core object to its counterpart in an external system.
    Required to avoid hardcoded mapping across the codebase (08-integration-contracts.md §13).
    """
    externalSystem: str         # erp | litefarm | crm | logistics | payment
    externalObjectType: str     # e.g. "sales_order", "farm_plot", "contact"
    externalObjectId: str
    internalObjectType: str     # e.g. "order", "plot", "customer"
    internalObjectId: str
    syncStatus: SyncStatus
    lastSyncedAt: str | None = None


class RegisterExternalMappingRequest(BaseModel):
    externalSystem: str
    externalObjectType: str
    externalObjectId: str
    internalObjectType: str
    internalObjectId: str


class ExternalMappingResponse(BaseModel):
    data: ExternalMappingRecord


class InventoryMovementRecord(BaseModel):
    """
    Append-only log of every quantity change on a lot.
    Required for auditability and to derive available_qty deterministically
    (04-canonical-data-model.md §4.11).
    """
    inventoryMovementId: str
    movementType: str           # release | reserve | reserve_release | consume | adjust | discard | return
    lotId: str
    relatedObjectType: str | None = None   # order | allocation | adjustment
    relatedObjectId: str | None = None
    qty: float
    unit: str
    occurredAt: str
    createdBy: str | None = None
    reasonCode: str | None = None


class ProductSKU(BaseModel):
    """
    Commercial unit used for sales, preorders, and lot linking.
    Source of truth: Agri OS Core (phase 1). May transfer to ERP item master later
    (04-canonical-data-model.md §4.6).
    """
    productSkuId: str
    skuCode: str
    skuName: str
    unit: str
    status: str = "active"
    category: str | None = None
    packSize: float | None = None
    defaultPrice: float | None = None
    isPreorderSupported: bool = False
