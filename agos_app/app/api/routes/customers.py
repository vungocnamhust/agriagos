from uuid import UUID

from fastapi import APIRouter, Query, Request

from app.api.routes._meta import apply_request_correlation, request_meta
from app.models.common import ErrorResponse
from app.models.customers import (
    CreateCustomerRequest,
    CustomerDuplicateCandidateListResponse,
    CustomerDuplicateCandidateSummary,
    CustomerDetail,
    CustomerListResponse,
    CustomerResponse,
    PreferenceResponse,
    ReviewDuplicateCandidateRequest,
    UpdateCustomerRequest,
    UpsertPreferenceRequest,
)
from app.services import customers as svc

router = APIRouter()


CUSTOMER_ERROR_RESPONSES = {
    403: {"model": ErrorResponse, "description": "Forbidden"},
    404: {"model": ErrorResponse, "description": "Aggregate not found"},
    409: {"model": ErrorResponse, "description": "Conflict"},
    422: {"model": ErrorResponse, "description": "Validation error"},
}
CREATE_CUSTOMER_ERROR_RESPONSES = {
    403: CUSTOMER_ERROR_RESPONSES[403],
    409: CUSTOMER_ERROR_RESPONSES[409],
    422: CUSTOMER_ERROR_RESPONSES[422],
}


@router.post("", response_model=CustomerResponse, status_code=201, responses=CREATE_CUSTOMER_ERROR_RESPONSES)
def create_customer(request: Request, payload: CreateCustomerRequest) -> CustomerResponse:
    return svc.create_customer(apply_request_correlation(request, payload))


@router.get("", response_model=CustomerListResponse, responses={403: CUSTOMER_ERROR_RESPONSES[403], 422: CUSTOMER_ERROR_RESPONSES[422]})
def list_customers(
    request: Request,
    phone: str | None = None,
    q: str | None = None,
    tag: str | None = Query(default=None, pattern=r"[A-Za-z0-9_-]+"),
) -> CustomerListResponse:
    return CustomerListResponse(items=svc.list_customers_for_actor(phone, q, tag, meta=request_meta(request)))


@router.get("/duplicate-candidates", response_model=CustomerDuplicateCandidateListResponse, responses={403: CUSTOMER_ERROR_RESPONSES[403]})
def list_duplicate_candidates(request: Request) -> CustomerDuplicateCandidateListResponse:
    return CustomerDuplicateCandidateListResponse(items=svc.list_duplicate_candidates_for_actor(meta=request_meta(request)))


@router.get("/{customer_id}", response_model=CustomerDetail, responses={403: CUSTOMER_ERROR_RESPONSES[403], 404: CUSTOMER_ERROR_RESPONSES[404], 422: CUSTOMER_ERROR_RESPONSES[422]})
def get_customer(customer_id: UUID, request: Request) -> CustomerDetail:
    return svc.get_customer_for_actor(str(customer_id), meta=request_meta(request))


@router.patch("/{customer_id}", response_model=CustomerDetail, responses={403: CUSTOMER_ERROR_RESPONSES[403], 404: CUSTOMER_ERROR_RESPONSES[404], 422: CUSTOMER_ERROR_RESPONSES[422]})
def update_customer(
    customer_id: UUID,
    request: Request,
    payload: UpdateCustomerRequest,
) -> CustomerDetail:
    return svc.update_customer(str(customer_id), apply_request_correlation(request, payload))


@router.post("/{customer_id}/preferences", response_model=PreferenceResponse, responses={403: CUSTOMER_ERROR_RESPONSES[403], 404: CUSTOMER_ERROR_RESPONSES[404], 422: CUSTOMER_ERROR_RESPONSES[422]})
def upsert_customer_preference(
    customer_id: UUID,
    request: Request,
    payload: UpsertPreferenceRequest,
) -> PreferenceResponse:
    return svc.upsert_preference(str(customer_id), apply_request_correlation(request, payload))


@router.get("/{customer_id}/duplicate-candidates", response_model=CustomerDuplicateCandidateListResponse, responses={403: CUSTOMER_ERROR_RESPONSES[403], 404: CUSTOMER_ERROR_RESPONSES[404], 422: CUSTOMER_ERROR_RESPONSES[422]})
def list_customer_duplicate_candidates(customer_id: UUID, request: Request) -> CustomerDuplicateCandidateListResponse:
    return CustomerDuplicateCandidateListResponse(items=svc.list_customer_duplicate_candidates_for_actor(str(customer_id), meta=request_meta(request)))


@router.post("/duplicate-candidates/{candidate_id}/review", response_model=CustomerDuplicateCandidateSummary, responses={403: CUSTOMER_ERROR_RESPONSES[403], 404: CUSTOMER_ERROR_RESPONSES[404], 422: CUSTOMER_ERROR_RESPONSES[422]})
def review_duplicate_candidate(
    candidate_id: UUID,
    request: Request,
    payload: ReviewDuplicateCandidateRequest,
) -> CustomerDuplicateCandidateSummary:
    return svc.review_duplicate_candidate(str(candidate_id), apply_request_correlation(request, payload))
