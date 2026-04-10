# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agri OS** — an operating system for agricultural supply chain management. The current phase (Phase 1) is a deterministic core API: source of truth before any AI/agent layer is added.

## Development Commands

```bash
# Install dependencies
cd agos_app
pip install -r requirements.txt

# Run the API server
uvicorn app.main:app --reload

# API is available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

No test framework or linter is configured yet. The database layer (`app/db/session.py`) is a placeholder stub.

## Architecture

### Layer Model

The system has 6 layers (documented in `system_v1.md`):

1. **Input Channels** — Internal UI, CRM, Zalo/Facebook chat, admin dashboard
2. **Ingress & Normalization** — Schema standardization before processing
3. **Agri OS Core (Deterministic)** — This repo; the single source of truth
4. **Output** — QR/traceability, dashboards, packing lists, financial reports
5. **AI/Agent Layer** — Future orchestration (deliberately not built in Phase 1)
6. **Integrations** — Third-party systems

### Write Path

```
Command → Command Gateway (validate, RBAC, idempotency check)
        → Application Service (domain logic)
        → Policy/Workflow Engine (state machine transitions)
        → Event Store (append-only domain event)
        → Projection Workers (update read models)
        → Audit Log
```

No direct DB mutations — all state changes are recorded as domain events first.

### Read Path

Events → Projection Workers → Role-specific Read Models (BFF views)

### Code Layout

```
agos_app/
├── app/
│   ├── main.py           # FastAPI entrypoint, CORS, router mount
│   ├── api/
│   │   ├── router.py     # Aggregates 8 route groups under /api/v1/
│   │   └── routes/       # One file per domain (customers, orders, lots, farm, preorders, views, events, health)
│   ├── models/           # Pydantic v2 schemas (DTOs, not ORM models)
│   │   ├── common.py     # Shared: Meta, ErrorResponse, DomainEvent
│   │   └── *.py          # Per-domain schemas
│   ├── core/config.py    # App settings via pydantic-settings
│   └── db/session.py     # DB session stub (not yet implemented)
```

### Domain Entities

8 canonical types: `Farmer`, `Plot`, `CropCycle`, `CropTask`, `Lot/Batch`, `ProductSKU`, `Order`, `Customer`

### API Surface

All endpoints are under `/api/v1/`. Currently all route handlers return `TODO` stubs. The route groups are:

- `/health` — liveness check
- `/customers` — customer CRUD and preferences
- `/preorders` — pre-order management
- `/orders` — full order lifecycle (create → confirm → allocate → pack → ship → deliver / cancel)
- `/lots` — lot/batch management (harvest → release / block)
- `/farm` — farm and plot operations
- `/views` — read model projections (role-based BFF views)
- `/events` — domain event stream queries

## Key Design Principles

- **Deterministic core first, AI second** — the core must be reliable and event-sourced before any AI orchestration is layered on top.
- **Event-first writes** — state changes happen via domain events appended to an event store, never direct DB updates.
- **One truth, many views** — a single canonical data model; each consumer role sees a different projection.
- **Idempotency** — the Command Gateway must deduplicate commands before processing.

## Design Documentation

All design docs are in the repo root (written in Vietnamese):

| File | Content |
|------|---------|
| `system_v1.md` | 6-layer system vision |
| `determistic_layer_spec_v1.md` | Module specs for the deterministic core |
| `event_desc.md` | Domain event definitions and rationale |
| `minimal_requirement.md` | MVP data model requirements |
| `deterministic_core_diagram.md` | Mermaid diagrams for all core flows |
| `vibe_coding.md` | AI agent workflow and coding philosophy |
