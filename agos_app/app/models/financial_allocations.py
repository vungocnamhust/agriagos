"""Financial allocation DTOs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.common import Meta


class FinancialAllocationDetail(BaseModel):
    financialAllocationId: str
    projectScopeId: str
    organizationId: str
    sourceRecordType: Literal["cost_record"]
    sourceRecordId: str
    allocationBasis: Literal["manual_full", "manual_weighted"]
    allocationWeight: float
    allocatedAmount: float
    currency: str
    metadata: dict[str, str] = Field(default_factory=dict)
    createdAt: str | None = None


class CreateFinancialAllocationRequest(BaseModel):
    sourceRecordType: Literal["cost_record"]
    sourceRecordId: str
    allocationBasis: Literal["manual_full", "manual_weighted"]
    allocationWeight: float | None = Field(default=None, gt=0, le=1)
    meta: Meta | None = None

    @model_validator(mode="after")
    def validate_weighted_basis(self) -> "CreateFinancialAllocationRequest":
        if self.allocationBasis == "manual_weighted" and self.allocationWeight is None:
            raise ValueError("allocationWeight is required when allocationBasis is manual_weighted.")
        return self


class FinancialAllocationResponse(BaseModel):
    data: FinancialAllocationDetail


class FinancialAllocationListResponse(BaseModel):
    items: list[FinancialAllocationDetail]