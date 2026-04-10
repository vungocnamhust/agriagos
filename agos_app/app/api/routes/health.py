from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def get_health() -> dict:
    return {"status": "ok", "service": "agri-os-core", "version": "0.1.0"}
