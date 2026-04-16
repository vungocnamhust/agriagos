from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.common import Meta
from app.models.enums import SharedResourceStatus, SharedResourceType


class SharedResourceSummary(BaseModel):
    sharedResourceId: str
    organizationId: str
    resourceCode: str
    name: str
    resourceType: SharedResourceType
    status: SharedResourceStatus
    capacityValue: float | None = None
    capacityUnit: str | None = None
    createdAt: str | None = None


class SharedResourceDetail(SharedResourceSummary):
    description: str | None = None
    updatedAt: str | None = None


class CreateSharedResourceRequest(BaseModel):
    organizationId: str
    name: str = Field(min_length=1, max_length=200)
    resourceType: SharedResourceType
    capacityValue: float | None = Field(default=None, ge=0)
    capacityUnit: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=2000)
    meta: Meta | None = None


class AllocateSharedResourceRequest(BaseModel):
    projectScopeId: str
    allocationBasis: str = Field(min_length=1, max_length=50)
    allocatedCapacity: float = Field(gt=0)
    effectiveAt: str | None = None
    meta: Meta | None = None


class ReleaseSharedResourceAllocationRequest(BaseModel):
    releasedCapacity: float = Field(gt=0)
    meta: Meta | None = None


class SharedResourceAllocationDetail(BaseModel):
    allocationId: str
    sharedResourceId: str
    projectScopeId: str
    allocationBasis: str
    allocatedCapacity: float
    releasedCapacity: float
    status: str
    effectiveAt: str
    releasedAt: str | None = None
    createdAt: str | None = None
    updatedAt: str | None = None


class SharedResourceResponse(BaseModel):
    data: SharedResourceDetail


class SharedResourceAllocationResponse(BaseModel):
    data: SharedResourceAllocationDetail


class SharedResourceListResponse(BaseModel):
    items: list[SharedResourceSummary]