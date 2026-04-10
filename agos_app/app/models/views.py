from pydantic import BaseModel
from app.models.customers import CustomerDetail
from app.models.preorders import PreorderDetail
from app.models.orders import OrderDetail
from app.models.farm import FarmView

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
    status: str

class PendingFulfillmentView(BaseModel):
    orderId: str
    orderCode: str
    customerName: str
    status: str
    shippingDeadline: str | None = None
