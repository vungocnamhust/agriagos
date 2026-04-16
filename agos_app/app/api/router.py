from fastapi import APIRouter
from app.api.routes import (
    actor_affiliations,
    actor_authority,
    audit,
    health,
    customers,
    organizations,
    project_scopes,
    shared_resources,
    preorders,
    orders,
    lots,
    farm,
    views,
    events,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(actor_authority.router, prefix="/api/v1/actors", tags=["ActorAuthority"])
api_router.include_router(actor_affiliations.router, prefix="/api/v1/affiliations", tags=["ActorAuthority"])
api_router.include_router(customers.router, prefix="/api/v1/customers", tags=["Customers"])
api_router.include_router(organizations.router, prefix="/api/v1/organizations", tags=["Organizations"])
api_router.include_router(project_scopes.router, prefix="/api/v1/projects", tags=["ProjectScopes"])
api_router.include_router(shared_resources.router, prefix="/api/v1/shared-resources", tags=["SharedResources"])
api_router.include_router(preorders.router, prefix="/api/v1/preorders", tags=["Preorders"])
api_router.include_router(orders.router, prefix="/api/v1/orders", tags=["Orders", "Allocations"])
api_router.include_router(lots.router, prefix="/api/v1/lots", tags=["Lots"])
api_router.include_router(farm.router, prefix="/api/v1/farm", tags=["Farm"])
api_router.include_router(views.router, prefix="/api/v1/views", tags=["Views"])
api_router.include_router(events.router, prefix="/api/v1/events", tags=["Events"])
api_router.include_router(audit.router, prefix="/api/v1/audit", tags=["Audit"])
