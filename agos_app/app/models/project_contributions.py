"""Project contribution ledger DTOs and request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.common import Meta
from app.models.enums import (
    ProjectAssignmentTargetType,
    ProjectContributionStatus,
    ProjectContributionVerificationSource,
    ProjectContributionVerificationStatus,
)


class ProjectContributionDetail(BaseModel):
    projectContributionEventId: str
    projectScopeId: str
    projectAssignmentId: str
    organizationId: str
    actorId: str
    actorType: str = "person"
    subjectType: ProjectAssignmentTargetType
    subjectId: str
    contributionType: str
    role: str
    verificationStatus: ProjectContributionVerificationStatus = ProjectContributionVerificationStatus.self_reported
    verificationSource: ProjectContributionVerificationSource = ProjectContributionVerificationSource.manual_submission
    verificationNote: str | None = None
    verificationEvidenceRef: str | None = None
    quantity: float
    unit: str
    estimatedValue: float | None = None
    currency: str | None = None
    status: ProjectContributionStatus
    confirmedBy: str | None = None
    confirmedAt: str | None = None
    rejectionReason: str | None = None
    source: str = "manual"
    metadata: dict[str, Any] = Field(default_factory=dict)
    createdAt: str | None = None


class ProjectContributionListResponse(BaseModel):
    items: list[ProjectContributionDetail]


class ProjectContributionResponse(BaseModel):
    data: ProjectContributionDetail


class RecordProjectContributionRequest(BaseModel):
    projectAssignmentId: str
    organizationId: str
    actorId: str
    actorType: str = Field(default="person", min_length=1, max_length=50)
    subjectType: ProjectAssignmentTargetType
    subjectId: str
    contributionType: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    verificationStatus: ProjectContributionVerificationStatus = ProjectContributionVerificationStatus.self_reported
    verificationSource: ProjectContributionVerificationSource = ProjectContributionVerificationSource.manual_submission
    verificationNote: str | None = Field(default=None, max_length=1000)
    verificationEvidenceRef: str | None = Field(default=None, max_length=255)
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=50)
    estimatedValue: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=1, max_length=10)
    source: str = Field(default="manual", min_length=1, max_length=100)
    metadata: dict[str, Any] | None = None
    meta: Meta | None = None


class ConfirmProjectContributionRequest(BaseModel):
    verificationNote: str | None = Field(default=None, max_length=1000)
    verificationEvidenceRef: str | None = Field(default=None, max_length=255)
    meta: Meta | None = None


class RejectProjectContributionRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)
    meta: Meta | None = None