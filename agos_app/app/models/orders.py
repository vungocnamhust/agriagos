from pydantic import BaseModel
from app.models.common import CommandMetaRequest, Meta
from app.models.enums import AllocationStatus, OrderLineStatus, OrderStatus, PaymentStatus
from app.models.project_assignments import ProjectAssignmentSummary

class OrderLine(BaseModel):
    orderLineId: str
    productSkuId: str
    orderedQty: float
    allocatedQty: float = 0
    packedQty: float = 0
    deliveredQty: float = 0
    unit: str
    status: OrderLineStatus = OrderLineStatus.open  # (06-state-transitions.md)
    sourcePreorderId: str | None = None

class OrderDetail(BaseModel):
    orderId: str
    orderCode: str
    organizationId: str | None = None
    customerId: str
    orderDate: str | None = None  # required in canonical model (04-canonical-data-model.md)
    channel: str
    status: OrderStatus  # (06-state-transitions.md)
    paymentStatus: PaymentStatus  # (06-state-transitions.md)
    deliveryDateExpected: str | None = None
    shippingAddress: str | None = None
    carrier: str | None = None
    trackingRef: str | None = None
    shippedAt: str | None = None
    deliveredAt: str | None = None
    proofRef: str | None = None
    failureReason: str | None = None
    note: str | None = None
    createdBy: str | None = None
    sourcePreorderFlag: bool = False
    version: int = 1
    lines: list[OrderLine]
    assignments: list[ProjectAssignmentSummary] = []

class CreateOrderLineRequest(BaseModel):
    productSkuId: str
    orderedQty: float
    unit: str
    sourcePreorderId: str | None = None

class CreateOrderRequest(BaseModel):
    organizationId: str | None = None
    customerId: str
    channel: str
    deliveryDateExpected: str | None = None
    shippingAddress: str | None = None
    paymentIntent: str | None = None
    lines: list[CreateOrderLineRequest]
    note: str | None = None
    meta: Meta | None = None

class OrderResponse(BaseModel):
    data: OrderDetail


class ConfirmOrderRequest(CommandMetaRequest):
    pass

class AllocateItem(BaseModel):
    orderLineId: str
    lotId: str
    allocatedQty: float

class AllocateOrderRequest(BaseModel):
    allocationPolicy: str = "manual"
    allocations: list[AllocateItem]
    meta: Meta | None = None

class AllocationItemResponse(BaseModel):
    allocationId: str
    orderLineId: str
    lotId: str
    allocatedQty: float
    allocatedAt: str | None = None  # (04-canonical-data-model.md)
    status: AllocationStatus  # (06-state-transitions.md)

class AllocationResponse(BaseModel):
    orderId: str
    allocations: list[AllocationItemResponse]


class AdjustAllocationRequest(BaseModel):
    newAllocatedQty: float
    reason: str | None = None
    approvalRef: str | None = None
    meta: Meta | None = None


class ReleaseAllocationRequest(BaseModel):
    reason: str | None = None
    approvalRef: str | None = None
    meta: Meta | None = None


class AllocationMutationResponse(BaseModel):
    orderId: str
    orderStatus: OrderStatus
    allocation: AllocationItemResponse

class PackQtyItem(BaseModel):
    orderLineId: str
    packedQty: float

class PackOrderRequest(BaseModel):
    packedQtySummary: list[PackQtyItem] = []
    note: str | None = None
    meta: Meta | None = None

class ShipOrderRequest(BaseModel):
    carrier: str
    trackingRef: str | None = None
    shippedAt: str | None = None
    meta: Meta | None = None


class DeliveredQtyItem(BaseModel):
    orderLineId: str
    deliveredQty: float


class DeliverOrderRequest(BaseModel):
    deliveredQtySummary: list[DeliveredQtyItem] = []
    deliveredAt: str | None = None
    proofRef: str | None = None
    note: str | None = None
    meta: Meta | None = None


class FailDeliveryRequest(BaseModel):
    failureReason: str
    note: str | None = None
    meta: Meta | None = None

class RequestCancelOrderRequest(BaseModel):
    reason: str
    meta: Meta | None = None

class CancelOrderRequest(BaseModel):
    reason: str | None = None
    approvalRef: str | None = None
    meta: Meta | None = None
