from fastapi import APIRouter, HTTPException
from app.models.customers import (
    CreateCustomerRequest,
    CustomerResponse,
    CustomerDetail,
    PreferenceResponse,
    UpsertPreferenceRequest,
)

router = APIRouter()

@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(payload: CreateCustomerRequest) -> CustomerResponse:
    # TODO: validate uniqueness, create canonical customer, append CustomerCreated event
    raise HTTPException(status_code=501, detail="Not implemented")

@router.get("")
def list_customers(phone: str | None = None, q: str | None = None, tag: str | None = None) -> dict:
    # TODO: query customer summaries
    return {"items": []}

@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str) -> CustomerDetail:
    # TODO: load customer detail
    raise HTTPException(status_code=501, detail="Not implemented")

@router.post("/{customer_id}/preferences", response_model=PreferenceResponse)
def upsert_customer_preference(customer_id: str, payload: UpsertPreferenceRequest) -> PreferenceResponse:
    # TODO: confirm preference according to policy, append CustomerPreferenceUpdated event
    raise HTTPException(status_code=501, detail="Not implemented")
