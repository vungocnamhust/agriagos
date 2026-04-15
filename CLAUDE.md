# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Agri OS** — an operating system for agricultural supply chain management. The current phase (Phase 1) is a deterministic core API: source of truth before any AI/agent layer is added.

## Development Commands

```bash
# Install dependencies
cd agos_app
pip install -r requirements.txt

# Install test/dev dependencies when working on pytest or TestClient coverage
pip install -r requirements-dev.txt

# Run the API server
uvicorn app.main:app --reload

# Run the PostgreSQL-backed customer_360 projection test
DATABASE_URL=postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos \
pytest tests/test_customer_360_view_integration.py -m postgres_integration

# Run the PostgreSQL-backed /views sweep (store helpers + HTTP endpoints)
DATABASE_URL=postgresql+psycopg://agriagos:agriagos@127.0.0.1:5436/agriagos \
pytest tests/test_view_board_integration.py -m postgres_integration

# API is available at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

Ruff is used for linting (`PYENV_VERSION=agos_3.10.14 ruff check agos_app/`). Runtime dependencies stay in `agos_app/requirements.txt`; pytest/TestClient dependencies now live in `agos_app/requirements-dev.txt`. Focused pytest coverage for deterministic-core write flows and `/views` read-model slices lives under `agos_app/tests/`, including PostgreSQL-backed integration coverage for `customer_360_view` and the `/views` board/store endpoint sweep in `tests/test_view_board_integration.py`. PostgreSQL migration scaffolding lives under `agos_app/alembic/`. The service layer now defaults to PostgreSQL when `POSTGRES_WRITE_PATH_ENABLED=true` and falls back to in-memory only for local simulation or tests. Recent authz rollout coverage also includes focused route/service tests for customers, preorders, orders, lots, and raw read surfaces.

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

Phase 1 runtime uses direct PostgreSQL writes plus event append. For write commands on the PostgreSQL path, state persistence, domain event append, audit decision logging, and idempotency snapshotting now share one transaction boundary. Projection workers remain a documented target architecture, not the default execution path.

### Read Path

Phase 1: direct PostgreSQL reads, SQL views, and service-shaped responses.
Phase 2 target: Events → Projection Workers → Role-specific Read Models (BFF views)

Current Phase 1 read-model reality:
- `available_lots_board`, `pending_fulfillment_board`, and `farm_summary_board` are direct PostgreSQL views exposed through `/api/v1/views/*`
- `customer_360_view` is now a nested JSON detail projection that matches the live `Customer360View` contract on the PostgreSQL path
- projection workers are still deferred; request-time freshness comes from direct SQL/view reads

### Code Layout

```
agos_app/
├── app/
│   ├── main.py           # FastAPI entrypoint: CorrelationIdMiddleware, ErrorResponse handlers, router mount
│   ├── api/
│   │   ├── router.py     # Aggregates 9 route groups under /api/v1/
│   │   └── routes/       # One file per domain (customers, organizations, orders, lots, farm, preorders, views, events, health)
│   ├── models/           # Pydantic v2 schemas (DTOs, not ORM models)
│   │   ├── common.py     # Shared: Meta, ErrorResponse, DomainEvent, HealthResponse, DomainEventListResponse
│   │   └── *.py          # Per-domain schemas
│   ├── core/
│   │   ├── codegen.py    # Centralized human-readable code generation (KH-, DT-, ORD-, LOT- formats)
│   │   ├── gateway.py    # Command Gateway: idempotency, state machine transitions
│   │   └── events.py     # Domain event factory (dotted-lowercase eventName + PascalCase eventType)
│   ├── services/         # Application services — one file per domain; audit.py centralizes audit reason registries and snapshot shaping
│   ├── store/
│   │   ├── _db.py        # DB connection + is_enabled() flag
│   │   ├── audit.py      # Audit log append/query against PostgreSQL
│   │   ├── customers.py  # Customer store operations
│   │   ├── events.py     # Domain event append/query against PostgreSQL
│   │   ├── farm.py       # Farm summary reads against PostgreSQL
│   │   ├── idempotency.py # Durable idempotency_records access
│   │   ├── lots.py       # Lot store operations
│   │   ├── organizations.py # Organization store operations
│   │   ├── orders.py     # Order store operations (atomic allocate/adjust/release/cancel)
│   │   ├── preorders.py  # Preorder store + quantity/history helpers for delivered/allocated/cancelled state
│   │   ├── postgres_sync.py  # Backward-compat re-export shim (do not add logic here)
│   │   ├── views.py      # DB-backed read-model queries for `/views`
│   │   └── memory.py     # In-memory fallback for local dev / unit tests
│   └── db/session.py     # SQLAlchemy engine/session wiring for PostgreSQL
├── alembic/              # Executable schema revisions for Phase 1 PostgreSQL
```

### Domain Entities

Phase 1 runtime stores the implemented core entities in PostgreSQL tables and store records such as `organizations`, `customers`, `preorders`, `sales_orders`, `sales_order_lines`, `product_skus`, `lots`, `plots`, and `crop_cycles`.

`Organization` is now implemented as a standalone canonical business aggregate for the legal-operating owner via ADR-012, with schema, CRUD/state routes, event emission, and additive `organization_id` propagation on farm-side canonical records plus the first commercial-side canonical records in place. The remaining intentional gap tracked in `docs/changelog/v1/divergence-ledger.md` entry `DL-20260415-01` is staged `organization_id` propagation into integration-facing and deferred relationship/read-model flows.

Architecture docs use canonical aliases such as `CustomerProfile`, `Preorder`, `SalesOrder`, `SalesOrderLine`, `ProductSKU`, `LotBatch`, `Plot`, and `CropCycle` for cross-reference with business terms. They may also discuss future or broader entities such as `Farmer` and `CropTask`, but those are not yet implemented in the current Phase 1 runtime.

Vietnamese architecture docs sometimes use shorter business names such as `Customer`, `Order`, and `Lot`. For the mapping between business labels and implementation names, see `docs/changelog/v1/architecture/04-canonical-data-model.md`.

### API Surface

All endpoints are under `/api/v1/`. The route groups are:

- `/health` — liveness check
- `/customers` — customer CRUD and preferences
- `/organizations` — standalone organization CRUD and state transitions
- `/preorders` — pre-order management
- `/orders` — full order lifecycle (create → confirm → allocate → adjust/release allocation → pack → ship → deliver / fail-delivery / cancel)
- `/lots` — lot/batch management, evidence, and QC reviews
- `/farm` — farm and plot operations
- `/views` — read model projections (role-based BFF views)
- `/events` — domain event stream queries
- `/audit` — audit decision log queries

## Key Design Principles

- **Deterministic core first, AI second** — the core must be reliable and event-sourced before any AI orchestration is layered on top.
- **DB-first Phase 1 runtime** — state changes persist to PostgreSQL state tables and append domain events in the same service flow.
- **One truth, many views** — a single canonical data model; each consumer role sees a different projection.
- **Idempotency** — the Command Gateway must deduplicate commands before processing, backed by `idempotency_records` in PostgreSQL.

## HTTP Infrastructure (wired in Phase 1)

- **Correlation ID** — `CorrelationIdMiddleware` in `main.py` reads `X-Correlation-ID` from the request header (or generates a UUID) and writes it to `request.state.correlation_id`; echoed in every response header.
- **Error envelope** — all non-2xx responses use `ErrorResponse { code, message, correlationId }`. Two exception handlers in `main.py` cover `StarletteHTTPException` and `RequestValidationError`. Semantic codes (`CUSTOMER_*`, `ORDER_*`, `LOT_*`, `PREORDER_*`, `FARM_*`, `INVALID_*`) in the HTTPException detail are promoted directly; others map via `_STATUS_CODE_MAP`.
- **Actor context seam** — `app/api/routes/_meta.py` is the shared route adapter for protected surfaces. It can seed `Meta` from request state or headers such as `X-Actor-Id`, `X-Actor-Role`, `X-Bypass-Requested`, `X-External-Ref`, `X-Delegated-Actor-Id`, and `X-Delegated-Actor-Role`, and it merges missing fields into write payloads before service calls.
- **Typed routes** — every route declares an explicit `response_model`. Do not add a route without one.
- **Health** — `GET /health` returns `HealthResponse { status, service, version, checks }`. When `POSTGRES_WRITE_PATH_ENABLED=true`, `checks.db` reports a live `SELECT 1` result; otherwise `"disabled"`.

## Authz Reality

- **Phase 1 bypass stance** — the repo keeps the bypass mechanism in `Meta` and authz helpers, but no bypass lanes are enabled. Any bypass request must deny and audit instead of executing.
- **Role vocabulary** — `qc_reviewer` is a top-level business role for the QC lane. Do not collapse it into `ops`, `farm_manager`, or delegated agent behavior.
- **Shared read auth rollout** — protected read surfaces now flow through request-meta plus service-layer authz. This includes `/api/v1/events`, `/api/v1/views/*`, raw `/api/v1/farm/*`, `/api/v1/audit`, raw `/api/v1/customers*`, raw preorder reads, raw `/api/v1/orders*`, and raw `/api/v1/lots/{lot_id}` plus evidence/QC review readbacks.
- **Write auth rollout** — preorder, order, lot/QC, and customer write paths now enforce role checks in the service layer before state transitions or event append. The remaining explicit divergence is the packed-or-later order cancel approval contract tracked in `docs/changelog/v1/divergence-ledger.md`.

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
| `08-role-based-view-permission-diagram.md` | Role/view/command matrix, including Phase 1 `/views/*`, audit/event readbacks, and raw-surface protection notes |
| `09-sequence-preorder-placed.md` | End-to-end preorder placed sequence |
| `10-sequence-harvestedlot-to-lotreleased.md` | Lot harvest → release sequence |
| `11-sequence-orderallocated-to-orderdelivered.md` | Order allocation → delivery sequence |

**Key Phase 1 state machine facts** (source: `core/gateway.py`):
- Order: `draft → confirmed → allocated|partially_allocated → packed|partially_packed → shipped → delivered|partially_delivered|failed`; repeated `allocate` can move `confirmed -> partially_allocated` or `partially_allocated -> allocated`; repeated `pack` can move `allocated -> partially_packed|packed`, `partially_allocated -> partially_packed`, and `partially_packed -> packed`; `deliver` is explicit and is allowed only from `shipped` and `partially_delivered`; `fail_delivery` is allowed from `shipped` and `partially_delivered`; `cancel_requested` is allowed from `partially_allocated`, `allocated`, and `packed`, while direct cancel remains available from `draft` and `confirmed`
- Lot: create path can initialize `harvested` or `qc_pending`; gateway currently supports `harvested/qc_pending → released`, `harvested/qc_pending/released → blocked`, and `blocked → qc_pending` via unblock without reopening inventory
- Organization: created in `draft`; `activate` allows `draft|paused -> active`; `pause` allows `active -> paused`; `close` allows `draft|paused -> closed`; `closed` is terminal in the standalone aggregate slice
- Preorder: created in `draft`; `confirm → confirmed`; `activate → active`; `adjust` stays in current `confirmed` or `active` state; `cancel → cancelled`; `completed` remains a terminal system-derived state produced by delivery/quota consumption rather than a dedicated gateway action; `remainingQty` is allocatable balance `committedQty - allocatedQty - deliveredQty - cancelledQty`

**Key Phase 1 event names** (source: `core/events.py` + `services/`):
- Use dotted lowercase at runtime: `order.created`, `order.confirmed`, `order.allocated`, `order.partially_allocated`, `allocation.adjusted`, `allocation.released`, `lot.harvest.created`, `lot.processed.created`, `lot.adjusted`, `preorder.placed`
- Standalone Organization runtime events now include `organization.created`, `organization.updated`, `organization.activated`, `organization.paused`, and `organization.closed`
- Fulfillment runtime events now also include `order.packed`, `order.partially_packed`, `order.shipped`, `order.delivered`, `order.partially_delivered`, and `order.delivery_failed`
- Preorder runtime events now include `preorder.confirmed`, `preorder.activated`, `preorder.adjusted`, `preorder.cancelled`, `preorder.quota_consumed`, and `preorder.completed`
- `eventType` is auto-derived PascalCase: `OrderCreated`, `OrderConfirmed`, `OrderAllocated`, `OrderPartiallyAllocated`, `AllocationAdjusted`, `AllocationReleased`, `LotHarvestCreated`, `LotProcessedCreated`, `LotAdjusted`, `PreorderPlaced`
- Preorder detail now carries append-only `adjustmentHistory`, backed by the `preorder_adjustments` table on the PostgreSQL path

**Key Phase 1 allocation contract facts**:
- Public allocation commands now include `POST /api/v1/orders/{order_id}/allocate`, `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/adjust`, and `POST /api/v1/orders/{order_id}/allocations/{allocation_id}/release`
- PostgreSQL allocation and cancel paths now keep `sales_order_lines.allocated_qty`, `lots.available_qty/reserved_qty`, and `preorders.allocated_qty/remaining_qty` in sync inside the atomic store flow
- Fulfillment write commands now include `POST /api/v1/orders/{order_id}/pack`, `POST /api/v1/orders/{order_id}/ship`, `POST /api/v1/orders/{order_id}/deliver`, and `POST /api/v1/orders/{order_id}/fail-delivery`
- `sales_orders` now snapshots fulfillment metadata directly in Phase 1, including `carrier`, `tracking_ref`, `shipped_at`, `delivered_at`, `proof_ref`, `delivery_note`, and `failure_reason`

**Key Phase 1 audit facts**:
- `app/services/audit.py` is the shared audit normalization layer: reason-code registries live there, sensitive snapshots are projected there, and services should go through `append_domain_audit_decision()` instead of appending raw audit entries directly
- shared route/service authz denials now append audit decisions across protected raw read and write surfaces; prefer the shared request-meta seam plus service-owned deny/audit behavior over route-local branching
- `lot.release` is the first owner-backed non-terminal audit lane: missing `approvalRef` on sensitive release writes `decision=escalated` with `reason_code=approval_required`; PostgreSQL persistence failure writes `decision=failed` with `reason_code=persistence_failed`

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
