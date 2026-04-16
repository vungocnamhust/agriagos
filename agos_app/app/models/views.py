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
    organizationId: str | None = None
    productSkuId: str
    releasedQty: float
    availableQty: float
    status: LotStatus


class AvailableLotListResponse(BaseModel):
    items: list[AvailableLotView]


class FarmSummaryBoardItem(BaseModel):
    plotId: str
    plotCode: str
    plotOrganizationId: str | None = None
    plotName: str
    locationText: str | None = None
    areaValue: float
    areaUnit: str
    plotStatus: str
    cropCycleId: str | None = None
    cropCycleOrganizationId: str | None = None
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
    organizationId: str | None = None
    customerName: str
    status: Literal["confirmed", "allocated", "packed", "shipped"]
    shippingDeadline: str | None = None


class PendingFulfillmentListResponse(BaseModel):
    items: list[PendingFulfillmentView]


class ProjectContributionSummaryItem(BaseModel):
    projectScopeId: str
    projectScopeCode: str
    projectScopeName: str
    proposedCount: int
    confirmedCount: int
    rejectedCount: int
    confirmedQuantity: float
    confirmedEstimatedValue: float | None = None
    currency: str | None = None


class ProjectContributionSummaryResponse(BaseModel):
    items: list[ProjectContributionSummaryItem]


class ProjectPnlSummaryItem(BaseModel):
    projectScopeId: str
    projectScopeCode: str
    projectScopeName: str
    costRecordCount: int
    revenueRecordCount: int
    recognizedCostAmount: float
    recognizedRevenueNetAmount: float
    marginAmount: float
    currency: str | None = None


class ProjectPnlSummaryResponse(BaseModel):
    items: list[ProjectPnlSummaryItem]


class ProjectOrderAllocationSummaryItem(BaseModel):
    projectScopeId: str
    projectScopeCode: str
    projectScopeName: str
    assignedOrderCount: int
    allocatedOrderCount: int
    allocationCount: int
    activeAllocationCount: int
    releasedAllocationCount: int
    allocatedQty: float
    activeAllocatedQty: float
    releasedAllocatedQty: float
    unit: str | None = None


class ProjectOrderAllocationSummaryResponse(BaseModel):
    items: list[ProjectOrderAllocationSummaryItem]


class ProjectContributionLedgerItem(BaseModel):
    projectScopeId: str
    projectScopeCode: str
    projectScopeName: str
    projectContributionEventId: str
    projectAssignmentId: str
    assignmentTargetType: str
    assignmentTargetId: str
    actorId: str
    actorType: str
    subjectType: str
    subjectId: str
    contributionType: str
    role: str
    verificationStatus: str
    verificationSource: str
    quantity: float
    unit: str
    estimatedValue: float | None = None
    currency: str | None = None
    status: str
    createdAt: str | None = None
    confirmedAt: str | None = None
    confirmedBy: str | None = None


class ProjectContributionLedgerResponse(BaseModel):
    items: list[ProjectContributionLedgerItem]


class ProjectImpactedActorSummaryItem(BaseModel):
    projectScopeId: str
    projectScopeCode: str
    projectScopeName: str
    actorId: str
    actorType: str
    role: str
    contributionCount: int
    confirmedContributionCount: int
    proposedContributionCount: int
    rejectedContributionCount: int
    confirmedQuantity: float
    confirmedEstimatedValue: float | None = None
    currency: str | None = None


class ProjectImpactedActorSummaryResponse(BaseModel):
    items: list[ProjectImpactedActorSummaryItem]
    
class SharedResourceAllocationSummaryItem(BaseModel):
    sharedResourceId: str
    organizationId: str
    resourceCode: str
    name: str
    resourceType: str
    status: str
    capacityValue: float | None = None
    capacityUnit: str | None = None
    allocationCount: int
    activeAllocationCount: int
    allocatedCapacityTotal: float
    releasedCapacityTotal: float
    activeCapacityTotal: float
    utilizationPct: float | None = None

class SharedResourceAllocationSummaryResponse(BaseModel):
    items: list[SharedResourceAllocationSummaryItem]
