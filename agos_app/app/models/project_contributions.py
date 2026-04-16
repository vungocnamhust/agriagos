"""Project contribution ledger DTOs and request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.common import Meta
from app.models.enums import ProjectContributionStatus


class ProjectContributionDetail(BaseModel):
    projectContributionEventId: str
    projectScopeId: str
    projectAssignmentId: str
    organizationId: str
    actorId: str
    subjectType: str
    subjectId: str
    contributionType: str
    role: str
    quantity: float
    unit: str
    estimatedValue: float | None = None
    currency: str | None = None
    status: ProjectContributionStatus
    confirmedBy: str | None = None
    confirmedAt: str | None = None
    rejectionReason: str | None = None
    source: str = "manual"
    metadata: dict[str, str] = Field(default_factory=dict)
    createdAt: str | None = None


class ProjectContributionListResponse(BaseModel):
    items: list[ProjectContributionDetail]


class ProjectContributionResponse(BaseModel):
    data: ProjectContributionDetail


class RecordProjectContributionRequest(BaseModel):
    projectAssignmentId: str
    organizationId: str
    actorId: str
    subjectType: str
    subjectId: str
    contributionType: str
    role: str
    quantity: float
    unit: str
    estimatedValue: float | None = None
    currency: str | None = None
    source: str = "manual"
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class ConfirmProjectContributionRequest(BaseModel):
    meta: Meta | None = None


class RejectProjectContributionRequest(BaseModel):
    reason: str
    meta: Meta | None = None