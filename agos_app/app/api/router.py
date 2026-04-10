from fastapi import APIRouter
from app.api.routes import (
    health,
    customers,
    preorders,
    orders,
    lots,
    farm,
    views,
    events,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])
api_router.include_router(preorders.router, prefix="/api/v1/preorders", tags=["Preorders"])
api_router.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders", "Allocations"])
api_router.include_router(lots.router, prefix="/api/v1/lots", tags=["Lots"])
api_router.include_router(farm.router, prefix="/api/v1/farm", tags=["Farm"])
api_router.include_router(views.router, prefix="/api/v1/views", tags=["Views"])
api_router.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
