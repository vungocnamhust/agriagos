from typing import Literal

from pydantic import BaseModel, Field
from app.models.common import Meta
from app.models.enums import CustomerStatus

class CustomerSummary(BaseModel):
    customerId: str
    customerCode: str
    fullName: str
    phone: str
    status: CustomerStatus  # required: active | inactive | blocked (06-state-transitions.md)
    createdAt: str | None = None
    tags: list[str] = Field(default_factory=list)


class CustomerPreferenceItem(BaseModel):
    preferenceType: str
    preferenceValue: str
    source: str = "human"
    confidenceLevel: float = 1.0
    confirmedBy: str | None = None
    confirmedAt: str | None = None


class CustomerDuplicateCandidateSummary(BaseModel):
    candidateId: str
    primaryCustomerId: str
    suspectedCustomerId: str
    matchReason: str
    matchScore: float
    status: Literal["open", "reviewed_duplicate", "reviewed_distinct", "ignored"]
    detectedAt: str | None = None
    reviewedAt: str | None = None
    reviewedBy: str | None = None
    note: str | None = None

class CustomerDetail(CustomerSummary):
    channelSource: str | None = None
    defaultAddress: str | None = None
    district: str | None = None
    province: str | None = None
    notes: str | None = None
    lastOrderAt: str | None = None
    preferences: list[CustomerPreferenceItem] = Field(default_factory=list)
    duplicateCandidates: list[CustomerDuplicateCandidateSummary] = Field(default_factory=list)

class CreateCustomerRequest(BaseModel):
    fullName: str
    phone: str
    channelSource: str | None = None
    defaultAddress: str | None = None
    district: str | None = None
    province: str | None = None
    tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    meta: Meta | None = None


class UpdateCustomerRequest(BaseModel):
    fullName: str | None = None
    channelSource: str | None = None
    defaultAddress: str | None = None
    district: str | None = None
    province: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    meta: Meta | None = None

class CustomerResponse(BaseModel):
    data: CustomerSummary

class CustomerListResponse(BaseModel):
    items: list[CustomerSummary]


class CustomerDuplicateCandidateListResponse(BaseModel):
    items: list[CustomerDuplicateCandidateSummary]

class UpsertPreferenceRequest(BaseModel):
    preferenceType: str
    preferenceValue: str
    source: str = Field(default="human", json_schema_extra={"enum": ["human", "integration"]})
    confidenceLevel: float = 1.0
    meta: Meta | None = None

class PreferenceResponse(BaseModel):
    customerId: str
    preferenceType: str
    preferenceValue: str
    source: str = "human"
    confidenceLevel: float
    confirmedBy: str | None = None
    confirmedAt: str | None = None


class ReviewDuplicateCandidateRequest(BaseModel):
    status: Literal["reviewed_duplicate", "reviewed_distinct", "ignored"]
    note: str | None = None
    meta: Meta | None = None
