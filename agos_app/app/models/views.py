from typing import Literal

from pydantic import BaseModel
from app.models.customers import CustomerDetail
from app.models.enums import CropCycleStatus, GrowthStage, LotStatus
from app.models.orders import OrderDetail
from app.models.preorders import PreorderDetail

class CustomerPreferenceItem(BaseModel):
    preferenceType: str
    preferenceValue: str
    confidenceLevel: float

class Customer360View(BaseModel):
    customer: CustomerDetail
    activePreorders: list[PreorderDetail]
    recentOrders: list[OrderDetail]
    preferences: list[CustomerPreferenceItem]

class AvailableLotView(BaseModel):
    lotId: str
    lotCode: str
    productSkuId: str
    releasedQty: float
    availableQty: float
    status: LotStatus  # (06-state-transitions.md)

class AvailableLotListResponse(BaseModel):
    items: list[AvailableLotView]


class FarmSummaryBoardItem(BaseModel):
    plotId: str
    plotCode: str
    plotName: str
    locationText: str | None = None
    areaValue: float
    areaUnit: str
    plotStatus: str
    cropCycleId: str | None = None
    cropName: str | None = None
    growthStage: GrowthStage | None = None
    cropCycleStatus: CropCycleStatus | None = None
    expectedHarvestFrom: str | None = None
    expectedHarvestTo: str | None = None
    estimatedYieldQty: float | None = None


class FarmSummaryBoardResponse(BaseModel):
    items: list[FarmSummaryBoardItem]

class PendingFulfillmentView(BaseModel):
    orderId: str
    orderCode: str
    customerName: str
    status: Literal["confirmed", "allocated", "packed", "shipped"]
    shippingDeadline: str | None = None

class PendingFulfillmentListResponse(BaseModel):
    items: list[PendingFulfillmentView]
