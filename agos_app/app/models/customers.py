from pydantic import BaseModel
from app.models.common import Meta

class CustomerSummary(BaseModel):
    customerId: str
    customerCode: str
    fullName: str
    phone: str
    tags: list[str] = []

class CustomerDetail(CustomerSummary):
    channelSource: str | None = None
    defaultAddress: str | None = None
    notes: str | None = None
    status: str | None = None

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
