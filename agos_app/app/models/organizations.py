from __future__ import annotations

from pydantic import BaseModel

from app.models.common import Meta
from app.models.enums import OrganizationStatus, OrganizationType


class OrganizationSummary(BaseModel):
    organizationId: str
    organizationCode: str
    name: str
    organizationType: OrganizationType
    status: OrganizationStatus
    region: str | None = None
    createdAt: str | None = None


class OrganizationDetail(OrganizationSummary):
    localitySummary: str | None = None
    representativeName: str | None = None
    contactPhone: str | None = None
    contactEmail: str | None = None
    shortDescription: str | None = None
    updatedAt: str | None = None


class CreateOrganizationRequest(BaseModel):
    name: str
    organizationType: OrganizationType
    region: str | None = None
    localitySummary: str | None = None
    representativeName: str | None = None
    contactPhone: str | None = None
    contactEmail: str | None = None
    shortDescription: str | None = None
    meta: Meta | None = None


class UpdateOrganizationRequest(BaseModel):
    name: str | None = None
    region: str | None = None
    localitySummary: str | None = None
    representativeName: str | None = None
    contactPhone: str | None = None
    contactEmail: str | None = None
    shortDescription: str | None = None
    meta: Meta | None = None


class ActivateOrganizationRequest(BaseModel):
    meta: Meta | None = None


class PauseOrganizationRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class CloseOrganizationRequest(BaseModel):
    reason: str
    meta: Meta | None = None


class OrganizationResponse(BaseModel):
    data: OrganizationDetail


class OrganizationListResponse(BaseModel):
    items: list[OrganizationSummary]