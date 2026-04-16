"""Project scope economics DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.common import Meta


class ProjectCostRecordDetail(BaseModel):
    costRecordId: str
    projectScopeId: str
    organizationId: str
    costType: Literal["labor_payout"]
    amount: float
    currency: str
    recognizedAt: str
    sourceObjectType: Literal["project_contribution_event"]
    sourceObjectId: str
    attributionPolicy: Literal["direct_source_link"]
    metadata: dict[str, str] = Field(default_factory=dict)
    createdAt: str | None = None


class CreateProjectCostRecordRequest(BaseModel):
    costType: Literal["labor_payout"]
    amount: float
    currency: str
    recognizedAt: str
    sourceObjectType: Literal["project_contribution_event"]
    sourceObjectId: str
    attributionPolicy: Literal["direct_source_link"]
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class ProjectCostRecordResponse(BaseModel):
    data: ProjectCostRecordDetail


class ProjectCostRecordListResponse(BaseModel):
    items: list[ProjectCostRecordDetail]