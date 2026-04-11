from pydantic import BaseModel
from app.models.common import Meta
from app.models.enums import CustomerStatus

class CustomerSummary(BaseModel):
    customerId: str
    customerCode: str
    fullName: str
    phone: str
    status: CustomerStatus  # required: active | inactive | blocked (06-state-transitions.md)
    createdAt: str | None = None
    tags: list[str] = []

class CustomerDetail(CustomerSummary):
    channelSource: str | None = None
    defaultAddress: str | None = None
    district: str | None = None
    province: str | None = None
    notes: str | None = None
    lastOrderAt: str | None = None

class CreateCustomerRequest(BaseModel):
    fullName: str
    phone: str
    channelSource: str | None = None
    defaultAddress: str | None = None
    district: str | None = None
    province: str | None = None
    tags: list[str] = []
    notes: str | None = None
    meta: Meta | None = None

class CustomerResponse(BaseModel):
    data: CustomerSummary

class CustomerListResponse(BaseModel):
    items: list[CustomerSummary]

class UpsertPreferenceRequest(BaseModel):
    preferenceType: str
    preferenceValue: str
    source: str = "human"
    confidenceLevel: float = 1.0
    meta: Meta | None = None

class PreferenceResponse(BaseModel):
    customerId: str
    preferenceType: str
    preferenceValue: str
    confidenceLevel: float
