"""Project assignment DTOs and request/response models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.common import Meta
from app.models.enums import ProjectAssignmentTargetType


class ProjectAssignmentSummary(BaseModel):
    projectAssignmentId: str
    projectScopeId: str
    targetType: ProjectAssignmentTargetType
    targetId: str
    isPrimary: bool = False
    attributionWeight: float | None = None
    createdAt: str | None = None
    endedAt: str | None = None


class ProjectAssignmentDetail(ProjectAssignmentSummary):
    endedReason: str | None = None
    metadata: dict[str, str] | None = None


class CreateProjectAssignmentRequest(BaseModel):
    targetType: ProjectAssignmentTargetType
    targetId: str
    isPrimary: bool = False
    attributionWeight: float | None = Field(default=None, ge=0, le=1)
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class EndProjectAssignmentRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class ProjectAssignmentResponse(BaseModel):
    data: ProjectAssignmentDetail


class ProjectAssignmentListResponse(BaseModel):
    items: list[ProjectAssignmentSummary]