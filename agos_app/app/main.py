from fastapi import FastAPI
from app.api.router import api_router

app = FastAPI(
    title="Agri OS Core API",
    version="0.1.0",
    summary="Deterministic core API for Agri OS",
)

app.include_router(api_router)
