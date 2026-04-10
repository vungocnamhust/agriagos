from pydantic import BaseModel
from app.models.customers import CustomerDetail
from app.models.enums import LotStatus, OrderStatus
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

class PendingFulfillmentView(BaseModel):
    orderId: str
    orderCode: str
    customerName: str
    status: OrderStatus  # (06-state-transitions.md)
    shippingDeadline: str | None = None
