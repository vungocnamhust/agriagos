from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.models.common import HealthResponse
from app.store._db import SessionLocal, is_enabled

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    checks: dict[str, str] = {}
    overall: str = "ok"

    if is_enabled():
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
            checks["db"] = "ok"
        except Exception:
            checks["db"] = "unreachable"
            overall = "degraded"
    else:
        checks["db"] = "disabled"

    return HealthResponse(
        status=overall,  # type: ignore[arg-type]
        service="agri-os-core",
        version=settings.version,
        checks=checks,
    )
