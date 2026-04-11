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

Ruff is used for linting (`PYENV_VERSION=agos_3.10.14 ruff check agos_app/`). No test framework is configured yet. PostgreSQL migration scaffolding lives under `agos_app/alembic/`. The service layer now defaults to PostgreSQL when `POSTGRES_WRITE_PATH_ENABLED=true` and falls back to in-memory only for local simulation or tests.

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
        → Store Layer (state tables in PostgreSQL)
        → Domain Event Append (`domain_events`)
        → Audit / future projections
```

Phase 1 runtime uses direct PostgreSQL writes plus event append. Projection workers remain a documented target architecture, not the default execution path.

### Read Path

Phase 1: direct PostgreSQL reads, SQL views, and service-shaped responses.
Phase 2 target: Events → Projection Workers → Role-specific Read Models (BFF views)

### Code Layout

```
agos_app/
├── app/
│   ├── main.py           # FastAPI entrypoint, CORS, router mount
│   ├── api/
│   │   ├── router.py     # Aggregates 8 route groups under /api/v1/
│   │   └── routes/       # One file per domain (customers, orders, lots, farm, preorders, views, events, health)
│   ├── models/           # Pydantic v2 schemas (DTOs, not ORM models)
│   │   ├── common.py     # Shared: Meta, ErrorResponse, DomainEvent (includes tenantId placeholder)
│   │   └── *.py          # Per-domain schemas
│   ├── core/
│   │   ├── codegen.py    # Centralized human-readable code generation (KH-, DT-, ORD-, LOT- formats)
│   │   ├── gateway.py    # Command Gateway: idempotency, state machine transitions
│   │   └── events.py     # Domain event factory (dotted-lowercase eventName + PascalCase eventType)
│   ├── services/         # Application services — one file per domain
│   ├── store/
│   │   ├── _db.py        # DB connection + is_enabled() flag
│   │   ├── customers.py  # Customer store operations
│   │   ├── events.py     # Domain event append/query against PostgreSQL
│   │   ├── farm.py       # Farm summary reads against PostgreSQL
│   │   ├── idempotency.py # Durable idempotency_records access
│   │   ├── lots.py       # Lot store operations
│   │   ├── orders.py     # Order store operations (atomic cancel/allocate)
│   │   ├── preorders.py  # Preorder store + increment_delivered_qty_atomic (SSoT for delivered qty)
│   │   ├── postgres_sync.py  # Backward-compat re-export shim (do not add logic here)
│   │   ├── views.py      # DB-backed read-model queries for `/views`
│   │   └── memory.py     # In-memory fallback for local dev / unit tests
│   └── db/session.py     # SQLAlchemy engine/session wiring for PostgreSQL
├── alembic/              # Executable schema revisions for Phase 1 PostgreSQL
```

### Domain Entities

Canonical implementation names: `CustomerProfile`, `Preorder`, `SalesOrder`, `SalesOrderLine`, `ProductSKU`, `LotBatch`, `Plot`, `CropCycle`, `Farmer`, `CropTask`.

Vietnamese architecture docs sometimes use shorter business names such as `Customer`, `Order`, and `Lot`. For the mapping between business labels and implementation names, see `docs/changelog/v1/architecture/04-canonical-data-model.md`.

### API Surface

All endpoints are under `/api/v1/`. The route groups are:

- `/health` — liveness check
- `/customers` — customer CRUD and preferences
- `/preorders` — pre-order management
- `/orders` — full order lifecycle (create → confirm → allocate → pack → ship → deliver / cancel)
- `/lots` — lot/batch management, evidence, and QC reviews
- `/farm` — farm and plot operations
- `/views` — read model projections (role-based BFF views)
- `/events` — domain event stream queries

## Key Design Principles

- **Deterministic core first, AI second** — the core must be reliable and event-sourced before any AI orchestration is layered on top.
- **DB-first Phase 1 runtime** — state changes persist to PostgreSQL state tables and append domain events in the same service flow.
- **One truth, many views** — a single canonical data model; each consumer role sees a different projection.
- **Idempotency** — the Command Gateway must deduplicate commands before processing, backed by `idempotency_records` in PostgreSQL.

## Design Documentation

Core narrative docs live in two layers:

| Location | Purpose |
|------|---------|
| `system_v1.md` | 6-layer system vision |
| `determistic_layer_spec_v1.md` | Module specs for the deterministic core |
| `event_desc.md` | Domain event definitions and rationale |
| `minimal_requirement.md` | MVP data model requirements |
| `deterministic_core_diagram.md` | Mermaid diagrams for all core flows |
| `vibe_coding.md` | AI agent workflow and coding philosophy |
| `docs/changelog/v1/README.md` | index for the current architecture baseline |
| `docs/changelog/v1/architecture/` | phase-1 architecture set: vision, workflows, canonical data model, integration contracts, AI boundaries, migration path, and baseline sign-off |
| `docs/changelog/v1/architecture/naming-conventions.md` | frozen naming rules: entities, events, states, endpoints, DTOs, commands, modules |
| `docs/changelog/v1/architecture/coding-guardrails.md` | what must be correct from day 1 vs what can be stubbed in Phase 1 |
| `docs/changelog/v1/adrs/` | ADR set covering core architectural decisions |
| `docs/changelog/v1/openapi/agros-api-v1.0.yaml` | committed OpenAPI baseline — update in same commit as any API change |
| `docs/changelog/v1/diagram/` | Mermaid diagram baseline — see table below |

### Diagram Baseline (`docs/changelog/v1/diagram/`)

All diagrams use `[Phase 1 ✅]` / `[Phase 2 🔜]` labels to distinguish implemented vs. planned.

| File | What it covers |
|---|---|
| `01-system-context-diagram.md` | Actors, channels, external systems, Core, future AI layer |
| `02-domain-ownership-context-map.md` | SSoT boundaries — integration target architecture; Phase 1 note added |
| `03-canonical-data-model-erd.md` | All canonical entities incl. `PREORDER` and `PRODUCT_SKU`; Phase 1/2 legend |
| `04-event-storming-event-map.md` | Commands → Events with runtime dotted names; Phase 2 events labeled |
| `05-state-machines-croptask-lot-order.md` | All 4 state machines; Phase 1 actual vs. Phase 2 planned split |
| `06-command-policy-event-projection-flow.md` | Generic write path sequence |
| `07-integration-flow-litefarm-erp-crm-core.md` | Integration target; DLQ/SyncBack marked Phase 2 |
| `08-role-based-view-permission-diagram.md` | 7 roles, views, commands; Phase 1 `/views/*` endpoints table added |
| `09-sequence-preorder-placed.md` | End-to-end preorder placed sequence |
| `10-sequence-harvestedlot-to-lotreleased.md` | Lot harvest → release sequence |
| `11-sequence-orderallocated-to-orderdelivered.md` | Order allocation → delivery sequence |

**Key Phase 1 state machine facts** (source: `core/gateway.py`):
- Order: `draft → confirmed → allocated → packed → shipped → delivered`; cancel path from `draft`/`confirmed` directly; `cancel_requested` only from `allocated`/`packed`
- Lot: `harvested → qc_pending → released`, with `block` allowed from `harvested`, `qc_pending`, or `released`
- Preorder: created in `active`; `adjust` stays `active`; `cancel → cancelled`

**Key Phase 1 event names** (source: `core/events.py` + `services/`):
- Use dotted lowercase at runtime: `order.created`, `order.confirmed`, `lot.harvest.created`, `preorder.placed`
- `eventType` is auto-derived PascalCase: `OrderCreated`, `OrderConfirmed`, `LotHarvestCreated`, `PreorderPlaced`

When repo-root docs and `docs/changelog/v1/architecture/` overlap, treat the `docs/changelog/v1/architecture/` set as the working baseline for current deterministic-core decisions.

**`docs/architecture/` is an empty placeholder — all actual docs are under `docs/changelog/v1/architecture/`.**

## Knowledge Classification (end of each phase)

After completing a phase or significant task, classify new learnings before stopping:

**Add to CLAUDE.md** only if ALL are true:
- Applies to most future sessions in this repo
- Short (a rule, fact, or constraint — not a procedure)
- Worth the token cost every session

**Create a skill** if ANY are true:
- Multi-step workflow, checklist, or playbook
- Long reference material or examples
- Task-specific or manually invoked
- Benefits from arguments, allowed-tools, or isolated subagent execution

**Otherwise** — keep it only in the phase PR, ADR, or issue. Do not store it.
