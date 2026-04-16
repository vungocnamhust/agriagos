import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.models.common import ErrorResponse

app = FastAPI(
    title="Agri OS Core API",
    version="0.1.0",
    summary="Deterministic core API for Agri OS",
)

# --- Middleware -----------------------------------------------------------

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        cid = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


app.add_middleware(CorrelationIdMiddleware)

# --- Exception handlers --------------------------------------------------

_STATUS_CODE_MAP: dict[int, str] = {
    400: "BAD_REQUEST",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_ERROR",
}

_SEMANTIC_PREFIXES = (
    "CUSTOMER_", "ORDER_", "LOT_", "PREORDER_", "FARM_", "INVALID_",
)


def _detail_to_code(status: int, detail: str) -> str:
    upper = detail.upper()
    if any(upper.startswith(p) for p in _SEMANTIC_PREFIXES):
        return upper.replace(" ", "_")
    return _STATUS_CODE_MAP.get(status, "ERROR")


def _normalize_validation_errors(errors: list[dict]) -> list[dict]:
    normalized_errors: list[dict] = []
    for error in errors:
        normalized_error = dict(error)
        context = normalized_error.get("ctx")
        if isinstance(context, dict):
            normalized_error["ctx"] = {
                key: (str(value) if isinstance(value, BaseException) else value)
                for key, value in context.items()
            }
        normalized_errors.append(normalized_error)
    return normalized_errors


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    cid = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=_detail_to_code(exc.status_code, str(exc.detail)),
            message=str(exc.detail),
            correlationId=cid,
        ).model_dump(exclude_none=True),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    cid = getattr(request.state, "correlation_id", None)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            code="VALIDATION_ERROR",
            message="Request validation failed",
            correlationId=cid,
            details={"errors": _normalize_validation_errors(exc.errors())},
        ).model_dump(exclude_none=True),
    )


# --- Routers -------------------------------------------------------------

app.include_router(api_router)
