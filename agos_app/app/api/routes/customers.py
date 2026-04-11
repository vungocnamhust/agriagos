from fastapi import APIRouter

from app.models.customers import (
    CreateCustomerRequest,
    CustomerDetail,
    CustomerListResponse,
    CustomerResponse,
    PreferenceResponse,
    UpsertPreferenceRequest,
)
from app.services import customers as svc

router = APIRouter()


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(payload: CreateCustomerRequest) -> CustomerResponse:
    return svc.create_customer(payload)


@router.get("", response_model=CustomerListResponse)
def list_customers(
    phone: str | None = None,
    q: str | None = None,
    tag: str | None = None,
) -> CustomerListResponse:
    return CustomerListResponse(items=svc.list_customers(phone, q, tag))


@router.get("/{customer_id}", response_model=CustomerDetail)
def get_customer(customer_id: str) -> CustomerDetail:
    return svc.get_customer(customer_id)


@router.post("/{customer_id}/preferences", response_model=PreferenceResponse)
def upsert_customer_preference(
    customer_id: str,
    payload: UpsertPreferenceRequest,
) -> PreferenceResponse:
    return svc.upsert_preference(customer_id, payload)
