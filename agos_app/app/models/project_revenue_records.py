"""Project scope revenue DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.common import Meta


class ProjectRevenueRecordDetail(BaseModel):
    revenueRecordId: str
    projectScopeId: str
    organizationId: str
    customerId: str
    revenueType: Literal["delivered_order_sale"]
    grossAmount: float
    netAmount: float
    currency: str
    recognizedAt: str
    sourceObjectType: Literal["order"]
    sourceObjectId: str
    metadata: dict[str, str] = Field(default_factory=dict)
    createdAt: str | None = None


class CreateProjectRevenueRecordRequest(BaseModel):
    revenueType: Literal["delivered_order_sale"]
    grossAmount: float
    netAmount: float
    currency: str
    sourceObjectType: Literal["order"]
    sourceObjectId: str
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class ProjectRevenueRecordResponse(BaseModel):
    data: ProjectRevenueRecordDetail


class ProjectRevenueRecordListResponse(BaseModel):
    items: list[ProjectRevenueRecordDetail]