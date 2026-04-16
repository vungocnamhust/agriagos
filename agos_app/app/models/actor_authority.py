from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.models.common import Meta
from app.models.enums import (
    ActorAffiliationKind,
    ActorAffiliationStatus,
    ActorIdentityStatus,
    ActorIdentityType,
)


class ActorIdentityDetail(BaseModel):
    actorId: str
    actorCode: str
    actorType: ActorIdentityType
    displayName: str
    status: ActorIdentityStatus
    primaryPhone: str | None = None
    primaryEmail: str | None = None
    externalMappingsJson: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    createdAt: str | None = None
    updatedAt: str | None = None


class CreateActorIdentityRequest(BaseModel):
    actorType: ActorIdentityType
    displayName: str
    primaryPhone: str | None = None
    primaryEmail: str | None = None
    externalMappingsJson: dict[str, Any] = {}
    metadata: dict[str, Any] = {}
    meta: Meta | None = None


class ActorIdentityResponse(BaseModel):
    data: ActorIdentityDetail


class ActorAffiliationDetail(BaseModel):
    actorAffiliationId: str
    actorId: str
    organizationId: str | None = None
    projectScopeId: str | None = None
    affiliationKind: ActorAffiliationKind
    status: ActorAffiliationStatus
    effectiveAt: str
    endedAt: str | None = None
    confirmedBy: str | None = None
    confirmedAt: str | None = None
    metadata: dict[str, Any] = {}
    createdAt: str | None = None
    updatedAt: str | None = None


class CreateActorAffiliationRequest(BaseModel):
    actorId: str
    organizationId: str | None = None
    projectScopeId: str | None = None
    affiliationKind: ActorAffiliationKind
    effectiveAt: str
    metadata: dict[str, Any] = {}
    meta: Meta | None = None


class ActorAffiliationResponse(BaseModel):
    data: ActorAffiliationDetail