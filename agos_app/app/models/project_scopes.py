from __future__ import annotations

from pydantic import BaseModel

from app.models.common import Meta
from app.models.enums import ProjectScopeStatus, ProjectScopeType


class ProjectScopeSummary(BaseModel):
    projectScopeId: str
    organizationId: str
    projectScopeCode: str
    name: str
    projectScopeType: ProjectScopeType
    status: ProjectScopeStatus
    seasonYear: str | None = None
    ownerActorId: str | None = None
    createdAt: str | None = None


class ProjectScopeDetail(ProjectScopeSummary):
    description: str | None = None
    parentProjectScopeId: str | None = None
    metadata: dict[str, str] | None = None
    updatedAt: str | None = None


class CreateProjectScopeRequest(BaseModel):
    organizationId: str
    name: str
    projectScopeType: ProjectScopeType
    seasonYear: str | None = None
    ownerActorId: str | None = None
    description: str | None = None
    parentProjectScopeId: str | None = None
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class UpdateProjectScopeRequest(BaseModel):
    name: str | None = None
    seasonYear: str | None = None
    ownerActorId: str | None = None
    description: str | None = None
    parentProjectScopeId: str | None = None
    metadata: dict[str, str] | None = None
    meta: Meta | None = None


class ActivateProjectScopeRequest(BaseModel):
    meta: Meta | None = None


class PauseProjectScopeRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class CloseProjectScopeRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class ArchiveProjectScopeRequest(BaseModel):
    meta: Meta | None = None


class ProjectScopeResponse(BaseModel):
    data: ProjectScopeDetail


class ProjectScopeListResponse(BaseModel):
    items: list[ProjectScopeSummary]